import re
from typing import Dict, Any

from app.nodes.base import BaseNodeExecutor


def evaluate_condition(
    condition_str: str,
    variables: Dict[str, Any],
) -> bool:
    condition_str = condition_str.strip()
    if not condition_str:
        return False

    # 1. Contains operator
    if " contains " in condition_str.lower():
        parts = re.split(r"\s+contains\s+", condition_str, flags=re.IGNORECASE, maxsplit=1)
        if len(parts) == 2:
            var_name = parts[0].strip()
            expected = parts[1].strip().strip("\"'")
            actual = str(variables.get(var_name, ""))
            return expected.lower() in actual.lower()

    # 2. Comparison operators
    pattern = r"^(.+?)\s*(==|!=|>=|<=|>|<)\s*(.*)$"
    match = re.match(pattern, condition_str)
    if not match:
        return False

    var_name, operator, value_string = match.groups()
    var_name = var_name.strip()
    value_string = value_string.strip()

    # ----------------------------------------------------------
    # Parse comparison value
    # ----------------------------------------------------------
    if value_string.lower() == "true":
        expected_value = True
    elif value_string.lower() == "false":
        expected_value = False
    elif (
        (value_string.startswith("'") and value_string.endswith("'"))
        or (value_string.startswith('"') and value_string.endswith('"'))
    ):
        expected_value = value_string[1:-1]
    else:
        try:
            if "." in value_string:
                expected_value = float(value_string)
            else:
                expected_value = int(value_string)
        except ValueError:
            expected_value = value_string

    # ----------------------------------------------------------
    # Get variable
    # ----------------------------------------------------------
    actual_value = variables.get(var_name)

    # Boolean conversion
    if isinstance(actual_value, str) and isinstance(expected_value, bool):
        actual_value = (actual_value.lower() == "true")

    # Numeric conversion
    if isinstance(expected_value, (int, float)) and actual_value is not None:
        try:
            actual_value = type(expected_value)(actual_value)
        except (ValueError, TypeError):
            pass

    # ----------------------------------------------------------
    # Compare
    # ----------------------------------------------------------
    if operator == "==":
        if isinstance(actual_value, str) and isinstance(expected_value, str):
            return actual_value.strip().lower() == expected_value.strip().lower()
        return actual_value == expected_value

    if operator == "!=":
        if isinstance(actual_value, str) and isinstance(expected_value, str):
            return actual_value.strip().lower() != expected_value.strip().lower()
        return actual_value != expected_value

    if operator == ">":
        if actual_value is None:
            return False
        return actual_value > expected_value

    if operator == "<":
        if actual_value is None:
            return False
        return actual_value < expected_value

    if operator == ">=":
        if actual_value is None:
            return False
        return actual_value >= expected_value

    if operator == "<=":
        if actual_value is None:
            return False
        return actual_value <= expected_value

    return False


class ConditionNodeExecutor(BaseNodeExecutor):

    def execute(
        self,
        node_config: Dict[str, Any],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:

        config = node_config.get("config") or node_config.get("data") or {}

        condition = (
            config.get("condition")
            or node_config.get("condition")
            or ""
        )
        condition = str(condition).strip()

        variables = state.get("variables", {}) or {}

        try:
            result = evaluate_condition(condition, variables)
        except Exception:
            result = False

        explicit_true = config.get("true_node") or node_config.get("true_node")
        explicit_false = config.get("false_node") or node_config.get("false_node")

        state["_route"] = "true" if result else "false"
        state["_route_index"] = 0 if result else 1
        if result and explicit_true:
            state["current_node"] = explicit_true
        elif not result and explicit_false:
            state["current_node"] = explicit_false

        state["status"] = "running"
        return state