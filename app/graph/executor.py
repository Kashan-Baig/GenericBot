import logging
from typing import Dict, Any, Optional, List

from app.graph.state import ChatState
from app.flows.loader import load_flow
from app.nodes import get_node_executor

logger = logging.getLogger("flow_engine.executor")


def get_node_by_id(
    flow: Dict[str, Any],
    node_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not node_id:
        return None

    for node in flow.get("nodes", []):
        if node.get("id") == node_id:
            return node

    return None


def get_next_nodes(
    flow: Dict[str, Any],
    current_node_id: Optional[str],
) -> List[str]:
    """
    Resolve outgoing connections from both edges list and node next_node attributes.
    """
    if not current_node_id:
        return []

    node = get_node_by_id(flow, current_node_id)
    next_nodes: List[str] = []

    # 1. Check edges
    for edge in flow.get("edges", []):
        if edge.get("source") == current_node_id:
            target = edge.get("target")
            if target and target not in next_nodes:
                next_nodes.append(target)

    # 2. Check explicit next_node on node
    if node:
        cfg = node.get("config") or node.get("data") or {}
        explicit_next = node.get("next_node") or cfg.get("next_node")
        if explicit_next and explicit_next not in next_nodes:
            next_nodes.append(explicit_next)

    return next_nodes


def get_routed_next_node(flow: Dict[str, Any], current_node_id: Optional[str], route: Optional[str], route_index: Optional[int] = None) -> Optional[str]:
    """Resolve a branch edge by label, then by deterministic output order."""
    if not current_node_id or not route:
        return None
    node = get_node_by_id(flow, current_node_id) or {}
    node_type = str(node.get("type", "")).lower().strip()
    outgoing = [e for e in flow.get("edges", []) if e.get("source") == current_node_id and e.get("target")]
    wanted = str(route).strip().lower()
    for edge in outgoing:
        label = str(edge.get("label") or "").strip().lower()
        if label == wanted:
            return edge.get("target")
    if route_index is not None and 0 <= route_index < len(outgoing):
        return outgoing[route_index].get("target")
    if node_type in {"switch", "for_each", "foreach", "loop"}:
        if wanted == "default" and outgoing:
            return outgoing[-1].get("target")
        if node_type in {"for_each", "foreach", "loop"}:
            config = node.get("config") or node.get("data") or {}
            if wanted == "each":
                return (
                    node.get("each_next_node")
                    or config.get("each_next_node")
                    or next((e.get("target") for e in outgoing if str(e.get("sourceHandle", "")).lower() == "each"), None)
                )
            if wanted == "done":
                return (
                    node.get("done_next_node")
                    or config.get("done_next_node")
                    or next((e.get("target") for e in outgoing if str(e.get("sourceHandle", "")).lower() == "done"), None)
                )
    return None


def get_next_node(
    flow: Dict[str, Any],
    current_node_id: Optional[str],
) -> Optional[str]:
    """
    Return the next node target for current_node_id.
    """
    node = get_node_by_id(flow, current_node_id)
    if node:
        cfg = node.get("config") or node.get("data") or {}
        explicit_next = node.get("next_node") or cfg.get("next_node")
        if explicit_next:
            return explicit_next

    nodes = get_next_nodes(flow, current_node_id)
    if nodes:
        return nodes[0]

    return None


def find_start_node(
    flow: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    nodes = flow.get("nodes", [])

    for node in nodes:
        if str(node.get("type", "")).lower() == "start":
            return node

    for node in nodes:
        if str(node.get("id", "")).lower() == "start":
            return node

    if nodes:
        return nodes[0]

    return None


def execute_current_node(state: ChatState) -> ChatState:
    """
    Execute exactly one logical node.
    """
    conversation_id = state.get("conversation_id", "unknown")
    flow_id = state.get("flow_id")

    if not flow_id:
        state["status"] = "error"
        state["response"] = "Error: No flow_id specified in state."
        return state

    flow = load_flow(flow_id)

    if not flow:
        state["status"] = "error"
        state["response"] = f"Error: Flow '{flow_id}' not found."
        return state

    nodes = flow.get("nodes", [])

    if not isinstance(nodes, list) or not nodes:
        state["status"] = "completed"
        state["current_node"] = "END"
        return state

    # ----------------------------------------------------------
    # Resolve START
    # ----------------------------------------------------------
    current_node_id = state.get("current_node")

    if not current_node_id or current_node_id == "START":
        start_node = find_start_node(flow)

        if not start_node:
            state["status"] = "error"
            state["response"] = f"Error: No start node found in flow '{flow_id}'."
            return state

        current_node_id = start_node.get("id")

        if not current_node_id:
            state["status"] = "error"
            state["response"] = "Error: Start node has no id."
            return state

        state["current_node"] = current_node_id

    if current_node_id == "END":
        # An END node can be used as the terminal node of a loop body.
        # If a For Each runtime is active, reaching END means "finish this
        # iteration and advance the loop" rather than completing the whole
        # workflow. The For Each node itself decides whether to continue
        # (Each) or exit (Done). A real workflow END is only completed when
        # there is no active loop runtime.
        loops = state.get("_loops") or {}
        if loops:
            active_loop_id = next(reversed(loops), None)
            if active_loop_id and get_node_by_id(flow, active_loop_id):
                state["current_node"] = active_loop_id
                state["status"] = "running"
                current_node_id = active_loop_id
            else:
                state["status"] = "completed"
                return state
        else:
            state["status"] = "completed"
            return state

    # ----------------------------------------------------------
    # Resolve current node config
    # ----------------------------------------------------------
    node_config = get_node_by_id(flow, current_node_id)

    if not node_config:
        state["status"] = "completed"
        state["current_node"] = "END"
        return state

    node_type = str(node_config.get("type", "")).lower().strip()

    if not node_type:
        state["status"] = "error"
        state["response"] = f"Error: Node '{current_node_id}' has no type."
        return state

    executor = get_node_executor(node_type)

    if not executor:
        state["status"] = "error"
        state["response"] = f"Error: Node executor for type '{node_type}' not found."
        return state

    logger.info(
        f"[NODE EXEC START] conv_id='{conversation_id}' | node_id='{current_node_id}' | "
        f"type='{node_type}' | status='{state.get('status')}' | variables={state.get('variables', {})}"
    )

    # ----------------------------------------------------------
    # Execute node
    # ----------------------------------------------------------
    try:
        updated_state = executor.execute(node_config, state)

        # ------------------------------------------------------
        # If executor didn't set next node and state is running,
        # resolve next node from edges / flow config.
        # ------------------------------------------------------
        if updated_state.get("status") == "running":
            # Branching nodes can return a route (true/false, case value, default).
            # Prefer an explicitly selected current_node, then fall back to a labeled edge.
            route = updated_state.pop("_route", None)
            route_index = updated_state.pop("_route_index", None)
            if route and updated_state.get("current_node") == current_node_id:
                routed = get_routed_next_node(flow, current_node_id, route, route_index)
                if routed:
                    updated_state["current_node"] = routed
                elif node_type in {"for_each", "foreach", "loop"}:
                    # A loop has two intentional exits. Never silently fall
                    # back to the first edge, because that could restart the
                    # loop forever when the Done output is not connected.
                    if route == "done":
                        updated_state["status"] = "completed"
                        updated_state["current_node"] = "END"
                    else:
                        raise ValueError(
                            "For Each node has no connection on its 'Each' output."
                        )

            if updated_state.get("current_node") == current_node_id:
                next_node = get_next_node(flow, current_node_id)
                if next_node:
                    updated_state["current_node"] = next_node
                else:
                    # A node with no outgoing edge is a valid terminal workflow.
                    updated_state["status"] = "completed"
                    updated_state["current_node"] = "END"

        logger.info(
            f"[NODE EXEC END] conv_id='{conversation_id}' | node_id='{current_node_id}' | "
            f"type='{node_type}' | current_node_after='{updated_state.get('current_node')}' | "
            f"status_after='{updated_state.get('status')}' | response='{updated_state.get('response')}'"
        )

        return updated_state

    except Exception as exc:
        logger.exception(f"Error executing node '{current_node_id}': {exc}")
        error_message = str(exc)
        state.setdefault("variables", {})["error"] = {
            "node_id": current_node_id,
            "message": error_message,
            "type": exc.__class__.__name__,
        }
        state["variables"]["error_message"] = error_message

        config = node_config.get("config") or node_config.get("data") or {}
        error_next = (
            node_config.get("error_next_node")
            or config.get("error_next_node")
        )
        if error_next and error_next != current_node_id:
            state["current_node"] = error_next
            state["status"] = "running"
            state["response"] = f"[Node error: {error_message}]"
        else:
            state["status"] = "error"
            state["response"] = f"Error executing node '{current_node_id}': {error_message}"
        return state