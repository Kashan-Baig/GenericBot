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
        # END
        # ------------------------------------------------------
        state["status"] = "completed"
        state["current_node"] = "END"
        state["user_input"] = ""

        return state