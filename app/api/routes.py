import logging
from fastapi import APIRouter, HTTPException, Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict

from app.flows.models import FlowConfig
from app.flows.loader import load_flow, save_flow, list_flows
from app.storage.conversation_store import store
from app.graph.graph import app_graph
from app.graph.executor import get_node_by_id
from app.nodes.base import render_template
from app.storage.credentials import list_credentials, create_credential, delete_credential, get_credential



logger = logging.getLogger("flow_engine.routes")

router = APIRouter()


# ============================================================
# REQUEST / RESPONSE MODELS
# ============================================================

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    conversation_id: str
    flow_id: Optional[str] = None
    message: Optional[str] = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    conversation_id: str
    response: str
    current_node: Optional[str]
    status: str
    variables: Dict[str, Any]

    # Useful for the frontend to know what it is waiting for
    waiting_for_input: bool = False
    input_prompt: Optional[str] = None
    finished: bool = False


# ============================================================
# CREDENTIALS API
# ============================================================

class CredentialCreateRequest(BaseModel):
    name: str
    provider: str
    api_key: str = ""
    api_url: Optional[str] = None
    # Generic secret bag for non-AI credentials, e.g. a database connection:
    # {"host": "...", "port": "5432", "database": "...", "username": "...", "password": "..."}
    # or a REST API: {"base_url": "...", "auth_header": "Authorization"}.
    extra: Optional[Dict[str, str]] = None


@router.get("/credentials", response_model=List[Dict[str, Any]])
async def get_credentials():
    return list_credentials()


@router.post("/credentials", response_model=Dict[str, Any])
async def add_credential(request: CredentialCreateRequest):
    try:
        return create_credential(
            request.name, request.provider, request.api_key, request.api_url, request.extra
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/credentials/{credential_id}")
async def remove_credential(credential_id: str):
    if not delete_credential(credential_id):
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"deleted": True}


# ============================================================
# DATA SOURCE TEST API
# ============================================================
#
# Lets the flow builder UI run a Data Source node's config against the real
# source (limited to a handful of rows) before saving the flow, the same way
# n8n's node "test step" button works.

class DataSourceTestRequest(BaseModel):
    source_type: str
    credential_id: Optional[str] = None
    table: Optional[str] = None
    query: Optional[str] = None
    endpoint: Optional[str] = None
    base_url: Optional[str] = None
    file_name: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    limit: int = 5


@router.post("/data-sources/test", response_model=Dict[str, Any])
async def test_data_source(request: DataSourceTestRequest):
    from app.nodes.data_source import DataSourceNodeExecutor

    node_config = {
        "id": "test",
        "type": "data_source",
        "config": {
            "source_type": request.source_type,
            "credential_id": request.credential_id,
            "table": request.table,
            "query": request.query,
            "endpoint": request.endpoint,
            "base_url": request.base_url,
            "file_name": request.file_name,
            "filters": request.filters or {},
            "limit": request.limit,
            "output_variable": "records",
        },
    }
    try:
        state = DataSourceNodeExecutor().execute(node_config, {"variables": {}})
        records = state["variables"]["records"]
        return {"success": True, "count": len(records), "sample": records[: request.limit]}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ============================================================
# CHAT ENDPOINT
# ============================================================

@router.post(
    "/chat",
    response_model=ChatResponse
)
async def chat(request: ChatRequest):

    conversation_id = request.conversation_id

    # ========================================================
    # 1. Resolve Flow ID
    # ========================================================

    existing_state = store.get_state(conversation_id)

    if existing_state:
        flow_id = (
            request.flow_id
            or existing_state.get("flow_id")
            or "demo_flow"
        )
    else:
        flow_id = request.flow_id or "demo_flow"

    # ========================================================
    # 2. Load Flow
    # ========================================================

    flow = load_flow(flow_id)

    if not flow:
        raise HTTPException(
            status_code=404,
            detail=f"Flow '{flow_id}' not found."
        )

    # ========================================================
    # IMPORTANT FIX
    # ========================================================
    # Some saved flows may contain:
    #
    #     "edges": null
    #
    # instead of:
    #
    #     "edges": []
    #
    # Make sure edges is ALWAYS iterable.
    # ========================================================

    flow["edges"] = flow.get("edges") or []

    # Also make sure nodes is safe
    flow["nodes"] = flow.get("nodes") or []

    # ========================================================
    # 3. Process Incoming Message
    # ========================================================

    message = (
        request.message.strip()
        if request.message is not None
        else None
    )

    user_input_provided = (
        message is not None and message != ""
    )

    user_message = message if message is not None else ""

    # ========================================================
    # 4. Prepare / Resume State
    # ========================================================

    if not existing_state:

        state: Dict[str, Any] = {
            "conversation_id": conversation_id,
            "flow_id": flow_id,
            "current_node": None,
            "user_input": user_message,
            "conversation_history": [],
            "variables": {},
            "response": "",
            "status": "running",
            "_turn_initial_node": None,
            "_turn_initial_status": None,
            "_turn_user_input_provided": user_input_provided,
        }

    else:

        state = existing_state

        # ----------------------------------------------------
        # Flow changed mid-conversation
        # ----------------------------------------------------

        if (
            request.flow_id
            and state.get("flow_id") != request.flow_id
        ):

            state = {
                "conversation_id": conversation_id,
                "flow_id": request.flow_id,
                "current_node": None,
                "user_input": user_message,
                "conversation_history": [],
                "variables": {},
                "response": "",
                "status": "running",
                "_turn_initial_node": None,
                "_turn_initial_status": None,
                "_turn_user_input_provided": user_input_provided,
            }

            flow_id = request.flow_id

        else:

            state["conversation_id"] = conversation_id

            # ------------------------------------------------------
            # A previous turn already ran this flow to completion.
            # A brand-new incoming message means the user wants to ask
            # something new — start a fresh run of the flow instead of
            # re-"executing" the END node, which has nothing left to do
            # and would just return an empty response forever after.
            # (This is what produced "The backend returned no message.
            # Current node: END." on the second message.)
            # ------------------------------------------------------
            if (
                user_input_provided
                and (state.get("status") == "completed" or state.get("current_node") == "END")
            ):
                state["current_node"] = None
                state["variables"] = {}
                state["status"] = "running"

            state["_turn_initial_node"] = (
                state.get("current_node")
            )

            state["_turn_initial_status"] = (
                state.get("status")
            )

            state["_turn_user_input_provided"] = (
                user_input_provided
            )

            state["user_input"] = user_message

            # Fresh response for this turn
            state["response"] = ""

            state["status"] = "running"

    # ========================================================
    # Make sure state fields exist
    # ========================================================

    state.setdefault("conversation_history", [])
    state.setdefault("variables", {})

    # ========================================================
    # 4b. Make the raw chat message available to EVERY node
    # ========================================================
    #
    # render_template() only ever looks at state["variables"], and
    # previously the only way a value landed there was an explicit
    # Input node capturing it into its configured `variable` (default
    # "user_input") while the flow was paused and waiting on that node.
    #
    # That means a flow like PostgreSQL -> AI -> END, which has no Input
    # node at all, could never reference the user's message in the AI
    # node's prompt: {{user_input}} simply wasn't set, so it rendered as
    # blank text and the model had no idea what was asked.
    #
    # {{user_message}} is a separate, always-on variable holding exactly
    # what the user typed this turn, regardless of flow shape. It does not
    # touch the Input node's own `variable` capture (still {{user_input}}
    # by default), so existing flows keep working unchanged.
    # ========================================================

    if user_message:
        state["variables"]["user_message"] = user_message

    # ========================================================
    # 5. Record User Message
    # ========================================================

    if user_message:

        state.setdefault(
            "conversation_history",
            []
        ).append({
            "role": "user",
            "type": "message",
            "content": user_message,
        })

    # ========================================================
    # 6. HANDLE BUTTON SELECTION
    # ========================================================
    #
    # If the previous turn stopped at a Buttons node,
    # the user's next message should select one of its
    # outgoing edges instead of executing the Buttons node
    # again.
    #
    # ========================================================

    current_node_id = state.get("current_node")

    if (
        existing_state
        and user_input_provided
        and current_node_id
    ):

        current_node = get_node_by_id(
            flow,
            current_node_id
        )

        if current_node:

            current_type = str(
                current_node.get("type", "")
            ).lower().strip()

            if current_type == "buttons":

                # ------------------------------------------------
                # Get button configuration
                # ------------------------------------------------

                config = (
                    current_node.get("config")
                    or current_node.get("data")
                    or current_node
                    or {}
                )

                # Prefer the node-level "options" list: it's the
                # canonical structured list (label/value/next_node).
                # "config.options" is often just a list of plain
                # label strings kept for the flow-builder UI and
                # has no next_node info, so it must NOT take
                # priority when it's present.
                options = (
                    current_node.get("options")
                    or config.get("options")
                    or []
                )

                selected_input = (
                    user_message
                    .strip()
                    .lower()
                )

                selected_target = None

                # ------------------------------------------------
                # Find matching button
                # ------------------------------------------------

                for index, option in enumerate(options):

                    if isinstance(option, dict):

                        label = str(
                            option.get("label")
                            or option.get("value")
                            or ""
                        ).strip()

                        value = str(
                            option.get("value")
                            or label.lower().replace(" ", "_")
                        ).strip()

                        option_target = (
                            option.get("next_node")
                        )

                    else:

                        label = str(option).strip()

                        value = (
                            label
                            .lower()
                            .replace(" ", "_")
                        )

                        option_target = None

                    # --------------------------------------------
                    # Possible inputs:
                    #
                    # Place Order
                    # place order
                    # place_order
                    # 1
                    # --------------------------------------------

                    matches = (
                        selected_input == label.lower()
                        or selected_input == value.lower()
                        or selected_input == str(index + 1)
                    )

                    if matches:

                        # First prefer next_node stored
                        # directly on the option.
                        if option_target:
                            selected_target = option_target

                        # Otherwise find matching edge below.
                        break

                # ------------------------------------------------
                # If option didn't contain next_node,
                # resolve target from flow edges.
                # ------------------------------------------------

                if selected_target is None:

                    # flow["edges"] was normalized above,
                    # so this is always safe.
                    for edge in flow.get("edges", []):

                        if not isinstance(edge, dict):
                            continue

                        if edge.get("source") != current_node_id:
                            continue

                        edge_label = str(
                            edge.get("label")
                            or edge.get("sourceHandle")
                            or edge.get("condition")
                            or ""
                        ).strip().lower()

                        if (
                            edge_label == selected_input
                            or edge_label.replace(" ", "_")
                            == selected_input
                        ):

                            selected_target = edge.get(
                                "target"
                            )

                            break

                # ------------------------------------------------
                # Also support numbered buttons
                # based on edge order.
                # ------------------------------------------------

                if selected_target is None:

                    try:

                        selected_index = int(
                            selected_input
                        ) - 1

                        outgoing_edges = [
                            edge
                            for edge in flow.get("edges", [])
                            if (
                                isinstance(edge, dict)
                                and edge.get("source")
                                == current_node_id
                            )
                        ]

                        if (
                            0 <= selected_index
                            < len(outgoing_edges)
                        ):

                            selected_target = (
                                outgoing_edges[
                                    selected_index
                                ].get("target")
                            )

                    except ValueError:
                        pass

                # ------------------------------------------------
                # Move to selected node
                # ------------------------------------------------

                if selected_target:

                    logger.info(
                        f"[BUTTON SELECT] "
                        f"conv_id='{conversation_id}' | "
                        f"button_node='{current_node_id}' | "
                        f"input='{user_message}' | "
                        f"next_node='{selected_target}'"
                    )

                    state["current_node"] = (
                        selected_target
                    )

                    state["status"] = "running"

                    # Mark that the button was consumed.
                    state["_button_selection"] = user_message

                else:

                    logger.warning(
                        f"[BUTTON NOT FOUND] "
                        f"conv_id='{conversation_id}' | "
                        f"node='{current_node_id}' | "
                        f"input='{user_message}'"
                    )

                    state["status"] = "waiting_for_input"

                    state["response"] = (
                        "Please select one of the available "
                        "options."
                    )

                    store.save_state(
                        conversation_id,
                        state
                    )

                    return ChatResponse(
                        conversation_id=conversation_id,
                        response=state["response"],
                        current_node=current_node_id,
                        status=state["status"],
                        variables=state.get(
                            "variables",
                            {}
                        ),
                        waiting_for_input=True,
                        input_prompt=None,
                        finished=False,
                    )

    # ========================================================
    # 7. Logging
    # ========================================================

    logger.info(
        f"[CHAT INCOMING] "
        f"conv_id='{conversation_id}' | "
        f"flow_id='{flow_id}' | "
        f"msg='{user_message}' | "
        f"initial_node='{state.get('_turn_initial_node')}' | "
        f"initial_status='{state.get('_turn_initial_status')}'"
    )

    # ========================================================
    # 8. Execute Flow via LangGraph
    # ========================================================

    try:

        final_state = app_graph.invoke(state)

    except Exception as e:

        logger.exception(
            f"Flow execution error for "
            f"conv_id='{conversation_id}': {e}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Flow execution error: {str(e)}"
        )

    # ========================================================
    # Safety check for final state
    # ========================================================

    if final_state is None:

        logger.error(
            f"LangGraph returned None for "
            f"conv_id='{conversation_id}'"
        )

        raise HTTPException(
            status_code=500,
            detail="Flow execution returned no state."
        )

    # ========================================================
    # 9. Extract Response Fields
    # ========================================================

    response_text = final_state.get(
        "response",
        ""
    )

    status = final_state.get(
        "status",
        "running"
    )

    current_node = final_state.get(
        "current_node"
    )

    variables = final_state.get(
        "variables",
        {}
    )

    if variables is None:
        variables = {}

    # ========================================================
    # 10. Determine Waiting / Finished
    # ========================================================

    waiting_for_input = (
        status in (
            "waiting_for_input",
            "waiting"
        )
    )

    finished = (
        status in (
            "completed",
            "end"
        )
    )

    # ========================================================
    # 11. Extract Input Prompt
    # ========================================================

    input_prompt = None

    if waiting_for_input and current_node:

        curr_node_config = get_node_by_id(
            flow,
            current_node
        )

        if curr_node_config:

            cfg = (
                curr_node_config.get("config")
                or curr_node_config.get("data")
                or {}
            )

            input_prompt = (
                cfg.get("text")
                or cfg.get("message")
                or curr_node_config.get("message")
                or curr_node_config.get("text")
            )

            if input_prompt:

                input_prompt = render_template(
                    input_prompt,
                    variables
                )

    # ========================================================
    # 12. Save State
    # ========================================================

    store.save_state(
        conversation_id,
        final_state
    )

    # ========================================================
    # 13. Logging
    # ========================================================

    logger.info(
        f"[CHAT OUTGOING] "
        f"conv_id='{conversation_id}' | "
        f"status='{status}' | "
        f"curr_node='{current_node}' | "
        f"waiting_for_input={waiting_for_input} | "
        f"response='{response_text}'"
    )

    # ========================================================
    # 14. Return Response
    # ========================================================

    return ChatResponse(
        conversation_id=conversation_id,
        response=response_text,
        current_node=current_node,
        status=status,
        variables=variables,
        waiting_for_input=waiting_for_input,
        input_prompt=input_prompt,
        finished=finished,
    )


# ============================================================
# FLOWS API
# ============================================================

@router.get(
    "/flows",
    response_model=List[str]
)
async def get_flows():

    return list_flows()


@router.get(
    "/flows/{flow_id}",
    response_model=Dict[str, Any]
)
async def get_flow(
    flow_id: str = Path(
        ...,
        description="The ID of the flow to inspect"
    )
):

    flow = load_flow(flow_id)

    if not flow:
        raise HTTPException(
            status_code=404,
            detail=f"Flow '{flow_id}' not found."
        )

    return flow


@router.post(
    "/flows",
    response_model=Dict[str, Any]
)
async def create_flow(
    flow: FlowConfig
):

    flow_data = flow.model_dump()

    # Normalize edges before saving
    flow_data["edges"] = flow_data.get("edges") or []

    # Normalize nodes too
    flow_data["nodes"] = flow_data.get("nodes") or []

    success = save_flow(flow_data)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to save flow configuration."
        )

    return flow_data


# ============================================================
# RENAME REQUEST MODEL
# ============================================================

class RenameFlowRequest(BaseModel):
    name: str


# ============================================================
# DELETE FLOW
# ============================================================

@router.delete(
    "/flows/{flow_id}"
)
async def delete_flow(
    flow_id: str = Path(
        ...,
        description="The ID of the flow to delete"
    )
):

    # Check that flow exists
    flow = load_flow(flow_id)

    if not flow:
        raise HTTPException(
            status_code=404,
            detail=f"Flow '{flow_id}' not found."
        )

    try:

        from app.flows.loader import delete_flow as delete_flow_file

        success = delete_flow_file(flow_id)

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete flow."
            )

        return {
            "success": True,
            "flow_id": flow_id,
            "message": f"Flow '{flow_id}' deleted successfully."
        }

    except HTTPException:
        raise

    except Exception as e:

        logger.exception(
            f"Failed to delete flow '{flow_id}': {e}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete flow: {str(e)}"
        )


# ============================================================
# RENAME FLOW
# ============================================================

@router.patch(
    "/flows/{flow_id}/rename"
)
async def rename_flow(
    flow_id: str = Path(
        ...,
        description="The ID of the flow to rename"
    ),
    request: RenameFlowRequest = None
):

    # Validate request
    if request is None or not request.name.strip():

        raise HTTPException(
            status_code=400,
            detail="Flow name cannot be empty."
        )

    # Load existing flow
    flow = load_flow(flow_id)

    if not flow:

        raise HTTPException(
            status_code=404,
            detail=f"Flow '{flow_id}' not found."
        )

    try:

        new_name = request.name.strip()

        # Update name
        flow["name"] = new_name

        # Keep flow structure valid
        flow["edges"] = flow.get("edges") or []
        flow["nodes"] = flow.get("nodes") or []

        # Save updated flow
        success = save_flow(flow)

        if not success:

            raise HTTPException(
                status_code=500,
                detail="Failed to rename flow."
            )

        return {
            "success": True,
            "flow_id": flow_id,
            "name": new_name,
            "message": f"Flow renamed to '{new_name}'.",
            "flow": flow,
        }

    except HTTPException:
        raise

    except Exception as e:

        logger.exception(
            f"Failed to rename flow '{flow_id}': {e}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to rename flow: {str(e)}"
        )