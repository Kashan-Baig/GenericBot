from typing import TypedDict, Dict, Any, List, Optional


class ChatState(TypedDict, total=False):

    conversation_id: str
    flow_id: str
    current_node: Optional[str]
    user_input: Optional[str]

    conversation_history: List[Dict[str, Any]]

    variables: Dict[str, Any]

    response: str

    status: str

    _flow: Dict[str, Any]
    _turn_initial_node: Optional[str]
    _turn_initial_status: Optional[str]
    _turn_user_input_provided: bool