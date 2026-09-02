from typing import Dict, Any

from app.nodes.base import BaseNodeExecutor, render_template


class InputNodeExecutor(BaseNodeExecutor):

    def execute(
        self,
        node_config: Dict[str, Any],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:

        node_id = node_config.get("id")
        config = node_config.get("config") or node_config.get("data") or {}

        # ------------------------------------------------------
        # 1. Read Prompt text
        # ------------------------------------------------------
        prompt = (
            config.get("text")
            or config.get("message")
            or node_config.get("message")
            or node_config.get("text")
            or ""
        )
        prompt = str(prompt).strip()

        # ------------------------------------------------------
        # 2. Read variable name
        # ------------------------------------------------------
        variable_name = (
            config.get("variable")
            or node_config.get("variable")
            or "user_input"
        )
        variable_name = str(variable_name).strip()

        # ------------------------------------------------------
        # 3. Check turn execution context
        # ------------------------------------------------------
        turn_initial_node = state.get("_turn_initial_node")
        turn_initial_status = state.get("_turn_initial_status")
        user_input_provided = state.get("_turn_user_input_provided", False)

        user_input = state.get("user_input")
        if user_input is not None:
            user_input = str(user_input).strip()
        else:
            user_input = ""

        is_resuming_at_this_node = (
            turn_initial_node == node_id
            and turn_initial_status in ("waiting_for_input", "waiting")
            and user_input_provided
            and bool(user_input)
        )

        # ======================================================
        # CASE 1: Resuming at this node with user's answer
        # ======================================================
        if is_resuming_at_this_node:
            variables = state.setdefault("variables", {})
            variables[variable_name] = user_input

            state.setdefault("conversation_history", []).append({
                "role": "user",
                "type": "input",
                "content": user_input,
                "variable": variable_name,
            })

            # Clear user_input so subsequent nodes in this turn do not consume it
            state["user_input"] = ""
            state["_turn_user_input_provided"] = False

            # Advance to next node
            state["status"] = "running"
            explicit_next = (
                node_config.get("next_node")
                or config.get("next_node")
            )
            if explicit_next:
                state["current_node"] = explicit_next

            return state

        # ======================================================
        # CASE 2: Reached for the first time in this turn (or no input)
        # SHOW PROMPT AND PAUSE EXECUTION AT THIS NODE.
        # ======================================================
        state["status"] = "waiting_for_input"
        state["current_node"] = node_id

        if prompt:
            rendered_prompt = render_template(prompt, state.get("variables", {}))
            existing_response = state.get("response", "")

            if existing_response:
                state["response"] = existing_response + "\n\n" + rendered_prompt
            else:
                state["response"] = rendered_prompt

            state.setdefault("conversation_history", []).append({
                "role": "assistant",
                "type": "input_prompt",
                "content": rendered_prompt,
            })

        return state