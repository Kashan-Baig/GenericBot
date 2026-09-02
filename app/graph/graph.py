from langgraph.graph import StateGraph, END

from app.graph.state import ChatState
from app.graph.executor import execute_current_node


def route_next_node(state: ChatState) -> str:

    status = state.get(
        "status",
        "running",
    )

    if status in (
        "waiting_for_input",
        "completed",
        "error",
    ):
        return "end"

    return "loop"


workflow = StateGraph(ChatState)

workflow.add_node(
    "execute_current_node",
    execute_current_node,
)

workflow.set_entry_point(
    "execute_current_node"
)

workflow.add_conditional_edges(
    "execute_current_node",
    route_next_node,
    {
        "loop": "execute_current_node",
        "end": END,
    },
)

app_graph = workflow.compile()