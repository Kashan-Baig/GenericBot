import os
import json
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger("flow_engine.loader")

from app.storage.credentials import create_credential
import logging

logger = logging.getLogger("flow_engine.loader")

FLOWS_DIR = os.path.dirname(os.path.abspath(__file__))

_in_memory_flows: Dict[str, Dict[str, Any]] = {}

def get_flow_path(flow_id: str) -> str:
    return os.path.join(FLOWS_DIR, f"{flow_id}.json")

def load_flow(flow_id: str) -> Optional[Dict[str, Any]]:
    if flow_id in _in_memory_flows:
        return _in_memory_flows[flow_id]
    
    path = get_flow_path(flow_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                flow_data = json.load(f)
                # Migrate legacy per-node API keys out of workflow JSON on load.
                migrated = False
                for node in flow_data.get("nodes", []):
                    config = node.get("config") or node.get("data") or {}
                    legacy_key = node.get("api_key") or config.get("api_key")
                    if legacy_key:
                        provider = node.get("provider") or config.get("provider") or "custom"
                        name = node.get("credential_name") or config.get("credential_name") or f"{str(provider).title()} credential"
                        try:
                            cred = create_credential(name, provider, legacy_key, node.get("api_url") or config.get("api_url"))
                            node["credential_id"] = cred["id"]
                            config.pop("api_key", None)
                            node.pop("api_key", None)
                            config["credential_id"] = cred["id"]
                            node["config"] = config
                            migrated = True
                        except Exception:
                            logger.exception("Failed to migrate legacy API key in flow '%s'", flow_id)
                _in_memory_flows[flow_id] = flow_data
                if migrated:
                    save_flow(flow_data)
                return flow_data
        except Exception:
            return None
    return None

def save_flow(flow_data: Dict[str, Any]) -> bool:
    flow_id = flow_data.get("flow_id")
    if not flow_id:
        return False
    
    # Never persist raw API keys inside workflow JSON.
    safe_flow = json.loads(json.dumps(flow_data))
    for node in safe_flow.get("nodes", []):
        config = node.get("config") or node.get("data") or {}
        if config.get("api_key") or node.get("api_key"):
            legacy_key = config.get("api_key") or node.get("api_key")
            provider = node.get("provider") or config.get("provider") or "custom"
            try:
                cred = create_credential(
                    config.get("credential_name") or f"{str(provider).title()} credential",
                    provider,
                    legacy_key,
                    node.get("api_url") or config.get("api_url"),
                )
                config["credential_id"] = cred["id"]
            except Exception:
                logger.exception("Failed to migrate API key while saving flow '%s'", flow_id)
            config.pop("api_key", None)
            node.pop("api_key", None)
        node["config"] = config
    _in_memory_flows[flow_id] = safe_flow
    flow_data = safe_flow
    
    path = get_flow_path(flow_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(flow_data, f, indent=2)
        return True
    except Exception:
        return False

def list_flows() -> list:
    flow_ids = set(_in_memory_flows.keys())
    if os.path.exists(FLOWS_DIR):
        for f in os.listdir(FLOWS_DIR):
            if f.endswith(".json"):
                flow_ids.add(f[:-5])
    return list(flow_ids)

def delete_flow(flow_id: str) -> bool:
    """
    Delete a flow configuration from storage.
    """

    path = get_flow_path(flow_id)

    if not os.path.exists(path):
        return False

    try:
        os.remove(path)
        return True

    except Exception as e:
        logger.exception(
            f"Failed to delete flow '{flow_id}': {e}"
        )
        return False
