from ast import pattern
from abc import ABC, abstractmethod
import re
from typing import Dict, Any


def _resolve_template_value(path: str, variables: Dict[str, Any]) -> Any:
    """Resolve simple nested paths such as ``record.name`` and ``items[0]``."""
    current: Any = variables
    tokens = [part for part in re.split(r"\.", path.strip()) if part]
    for token in tokens:
        match = re.match(r"^([^\[]+)(?:\[(\d+)\])?$", token.strip())
        if not match:
            return None
        key, index_text = match.group(1), match.group(2)
        if isinstance(current, dict):
            if key not in current:
                return None
            current = current[key]
        else:
            return None
        if index_text is not None:
            if not isinstance(current, (list, tuple)):
                return None
            index = int(index_text)
            if index >= len(current):
                return None
            current = current[index]
    return current


def render_template(template: str, variables: Dict[str, Any]) -> str:
    if not template or not isinstance(template, str):
        return ""

    if not variables:
        return template

    def replace_double(match: re.Match) -> str:
        value = _resolve_template_value(match.group(1), variables)
        return "" if value is None else str(value)

    def replace_single(match: re.Match) -> str:
        value = _resolve_template_value(match.group(1), variables)
        return match.group(0) if value is None else str(value)

    result = re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace_double, template)
    return re.sub(r"(?<!\{)\{\s*([^{}]+?)\s*\}(?!\})", replace_single, result)


class BaseNodeExecutor(ABC):
    @abstractmethod
    def execute(self, node_config: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes node logic and returns the updated state dict.
        """
        pass

