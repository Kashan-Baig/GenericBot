from typing import Dict, Any

from app.nodes.base import BaseNodeExecutor, render_template


class EndNodeExecutor(BaseNodeExecutor):

    def execute(
        self,
        node_config: Dict[str, Any],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:

        config = node_config.get("config") or node_config.get("data") or {}

        msg = (
            config.get("text")
            or config.get("message")
            or node_config.get("message")
            or node_config.get("text")
            or ""
        )
        msg = str(msg).strip()

        # ------------------------------------------------------
        # Optional final message
        # ------------------------------------------------------
        if msg:
            rendered_msg = render_template(msg, state.get("variables", {}))
            existing_response = state.get("response", "")

            if existing_response:
                state["response"] = (
                    existing_response
                    + "\n\n"
                    + rendered_msg
                )
            else:
                state["response"] = rendered_msg

            state.setdefault("conversation_history", []).append({
                "role": "assistant",
                "type": "end_message",
                "content": rendered_msg,
            })

        # ------------------------------------------------------
        # END — unless this End node is being used as the terminal
        # node of a loop body (for_each's docs explicitly support this:
        # "the final body node should connect back to the loop").
        #
        # If a loop is still active, reaching End here means "finish this
        # iteration", not "finish the whole workflow" — hand control back
        # to the innermost active loop so it can advance to the next item
        # (or exit for real via its own Done route once items run out).
        # Without this check, the very first loop iteration would reach
        # this node, immediately mark the workflow "completed", and the
        # remaining items would never be processed.
        # ------------------------------------------------------
        loops = state.get("_loops") or {}
        if loops:
            active_loop_id = next(reversed(loops), None)
            if active_loop_id:
                state["current_node"] = active_loop_id
                state["status"] = "running"
                return state

        state["status"] = "completed"
        state["current_node"] = "END"
        state["user_input"] = ""

        return state