from typing import Dict, Any

from app.nodes.base import BaseNodeExecutor, render_template


class SwitchNodeExecutor(BaseNodeExecutor):
    """Route execution to one of several configured cases.

    Config format:
      variable: "plan"
      cases: [
        {"value": "pro", "label": "Pro", "next_node": "node-id"},
        {"value": "free", "label": "Free", "next_node": "node-id"}
      ]
      default_next_node: "fallback-node"
    """

    def execute(self, node_config: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        config = node_config.get("config") or node_config.get("data") or {}
        variable = str(config.get("variable") or node_config.get("variable") or "").strip()
        value = (state.get("variables") or {}).get(variable)
        cases = config.get("cases") or node_config.get("cases") or []
        if not isinstance(cases, list):
            cases = []

        matched = None
        for case in cases:
            if not isinstance(case, dict):
                continue
            expected = case.get("value")
            if str(value).strip().lower() == str(expected).strip().lower():
                matched = case
                break

        if matched:
            match_index = cases.index(matched)
            state["_route"] = str(matched.get("value", ""))
            state["_route_index"] = match_index
            if matched.get("next_node"):
                state["current_node"] = matched["next_node"]
        else:
            default_next = config.get("default_next_node") or node_config.get("default_next_node")
            state["_route"] = "default"
            state["_route_index"] = len(cases)
            if default_next:
                state["current_node"] = default_next

        state["status"] = "running"
        state["variables"] = state.get("variables") or {}
        state["variables"]["switch_value"] = value
        return state
