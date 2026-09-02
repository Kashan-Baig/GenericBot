from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, ConfigDict


class ButtonOption(BaseModel):
    model_config = ConfigDict(extra="allow")

    label: str
    value: Optional[str] = None
    next_node: Optional[str] = None


class FlowNode(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: str  # start, message, buttons, input, condition, end, etc.
    message: Optional[str] = None
    text: Optional[str] = None
    options: Optional[List[Union[ButtonOption, Dict[str, Any]]]] = None
    variable: Optional[str] = None
    condition: Optional[str] = None
    true_node: Optional[str] = None
    false_node: Optional[str] = None
    next_node: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None


class FlowConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    flow_id: str
    nodes: List[Union[FlowNode, Dict[str, Any]]]
    edges: Optional[List[Dict[str, Any]]] = None

