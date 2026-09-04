"""Generic For Each / Loop node."""

from typing import Any, Dict

from app.nodes.base import BaseNodeExecutor


class ForEachNodeExecutor(BaseNodeExecutor):
    """Iterate a list and expose one item at a time.

    Connect the loop's ``Each`` output to the loop body. The final body node
    should connect back to the loop. The loop's ``Done`` output continues after
    all items have been processed.
    """

    def execute(self, node_config: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        config = node_config.get("config") or node_config.get("data") or {}
        variables = state.setdefault("variables", {})

        input_variable = str(config.get("input_variable") or "records").strip() or "records"
        item_variable = str(config.get("item_variable") or "current_item").strip() or "current_item"
        index_variable = str(config.get("index_variable") or "index").strip() or "index"

        loops = state.setdefault("_loops", {})
        loop_id = str(node_config.get("id") or "loop")
        runtime = loops.get(loop_id)

        if runtime is None:
            items = variables.get(input_variable)
            if items is None:
                raise ValueError(f"Loop input variable '{input_variable}' was not found.")
            if not isinstance(items, list):
                raise ValueError(
                    f"Loop input variable '{input_variable}' must contain a list, "
                    f"got {type(items).__name__}."
                )
            runtime = {"items": items, "index": 0}
            loops[loop_id] = runtime
        else:
            runtime["index"] = int(runtime.get("index", 0)) + 1

        items = runtime["items"]
        index = int(runtime["index"])

        if index >= len(items):
            loops.pop(loop_id, None)
            variables.pop(item_variable, None)
            variables.pop(index_variable, None)
            variables.pop(f"{item_variable}_number", None)
            state["_route"] = "done"
            state["status"] = "running"
            return state

        variables[item_variable] = items[index]
        variables[index_variable] = index
        variables[f"{item_variable}_number"] = index + 1
        state["_route"] = "each"
        state["status"] = "running"
        return state
