from typing import Dict, Any
from app.nodes.base import BaseNodeExecutor, render_template


class MessageNodeExecutor(BaseNodeExecutor):
    def execute(self, node_config: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        config = node_config.get("config") or node_config.get("data") or {}

        msg = (
            config.get("text")
            or config.get("message")
            or node_config.get("message")
            or node_config.get("text")
            or ""
        )
        msg = str(msg).strip()

        rendered_msg = render_template(msg, state.get("variables", {}))

        # Append message to current turn response
        if state.get("response"):
            state["response"] += "\n\n" + rendered_msg
        else:
            state["response"] = rendered_msg

        # Add to conversation history
        state.setdefault("conversation_history", []).append({
            "role": "assistant",
            "type": "message",
            "content": rendered_msg,
        })

        # Transition to next node if explicitly specified
        explicit_next = (
            node_config.get("next_node")
            or config.get("next_node")
        )
        if explicit_next:
            state["current_node"] = explicit_next

        state["status"] = "running"
        return state

