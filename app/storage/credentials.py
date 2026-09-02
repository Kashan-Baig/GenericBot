"""Encrypted credential storage for provider/API secrets.

Credentials are intentionally kept outside workflow JSON files. The store uses
Fernet encryption and a local key file (ignored by git) when no explicit
CREDENTIAL_ENCRYPTION_KEY is configured. For production, set
CREDENTIAL_ENCRYPTION_KEY in the server environment and use persistent secret
management/KMS rather than the local key file.
"""
import base64
import json
import os
import secrets
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet

STORAGE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = STORAGE_DIR / "credentials.json"
KEY_FILE = STORAGE_DIR / ".credential_key"
_lock = threading.Lock()


def _get_fernet() -> Fernet:
    raw = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "").strip()
    if raw:
        return Fernet(raw.encode())

    if KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip().encode()
    else:
        key = Fernet.generate_key()
        KEY_FILE.write_text(key.decode(), encoding="utf-8")
        try:
            os.chmod(KEY_FILE, 0o600)
        except OSError:
            pass
    return Fernet(key)


def _read() -> List[Dict[str, Any]]:
    if not CREDENTIALS_FILE.exists():
        return []
    try:
        data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write(data: List[Dict[str, Any]]) -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_credentials() -> List[Dict[str, Any]]:
    with _lock:
        result = []
        for item in _read():
            result.append({
                "id": item["id"],
                "name": item.get("name", item["id"]),
                "provider": item.get("provider", "custom"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "has_api_key": bool(item.get("api_key")),
            })
        return result


def create_credential(name: str, provider: str, api_key: str, api_url: Optional[str] = None) -> Dict[str, Any]:
    if not api_key or not api_key.strip():
        raise ValueError("API key is required")
    credential_id = f"cred_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    token = _get_fernet().encrypt(api_key.strip().encode()).decode()
    record = {
        "id": credential_id,
        "name": name.strip() or f"{provider.title()} credential",
        "provider": provider.strip().lower(),
        "api_key": token,
        "api_url": api_url or "",
        "created_at": now,
        "updated_at": now,
    }
    with _lock:
        data = _read()
        data.append(record)
        _write(data)
    return {k: v for k, v in record.items() if k not in {"api_key", "api_url"}}


def get_credential(credential_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        for item in _read():
            if item.get("id") != credential_id:
                continue
            try:
                api_key = _get_fernet().decrypt(item["api_key"].encode()).decode()
            except Exception as exc:
                raise RuntimeError("Unable to decrypt credential. Check CREDENTIAL_ENCRYPTION_KEY.") from exc
            return {
                "id": item["id"],
                "name": item.get("name", item["id"]),
                "provider": item.get("provider", "custom"),
                "api_key": api_key,
                "api_url": item.get("api_url", ""),
            }
    return None


def delete_credential(credential_id: str) -> bool:
    with _lock:
        data = _read()
        new_data = [item for item in data if item.get("id") != credential_id]
        if len(new_data) == len(data):
            return False
        _write(new_data)
        return True
