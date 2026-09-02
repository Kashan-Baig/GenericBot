import threading
import copy
from typing import Dict, Optional, Any

class MemoryConversationStore:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            state = self._store.get(conversation_id)
            if state:
                return copy.deepcopy(state)
            return None

    def save_state(self, conversation_id: str, state: Dict[str, Any]) -> None:
        with self._lock:
            self._store[conversation_id] = copy.deepcopy(state)

    def delete_state(self, conversation_id: str) -> None:
        with self._lock:
            if conversation_id in self._store:
                del self._store[conversation_id]

    def clear_all(self) -> None:
        with self._lock:
            self._store.clear()

store = MemoryConversationStore()
