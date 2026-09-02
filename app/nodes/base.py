from ast import pattern
from abc import ABC, abstractmethod
import re
from typing import Dict, Any


def render_template(template: str, variables: Dict[str, Any]) -> str:
    if not template or not isinstance(template, str):
        return ""

    if not variables:
        return template

    result = template
    for key, val in variables.items():
        val_str = str(val) if val is not None else ""
        # Match {{key}}, {{ key }}
        result = re.sub(rf"\{{\{{\s*{re.escape(str(key))}\s*\}}\}}", val_str, result)
        # Match {key}, { key } (not part of {{...}})
        pattern = r"(?<!\{)\{\s*" + re.escape(str(key)) + r"\s*\}(?!\})"

        result = re.sub(pattern, val_str, result)

    return result


class BaseNodeExecutor(ABC):
    @abstractmethod
    def execute(self, node_config: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes node logic and returns the updated state dict.
        """
        pass

