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
                "extra_keys": item.get("extra_keys", []),
            })
        return result


def create_credential(
    name: str,
    provider: str,
    api_key: str = "",
    api_url: Optional[str] = None,
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Create a credential.

    ``api_key``/``api_url`` cover the original AI-provider use case. ``extra``
    is a generic bag of additional secret fields (e.g. host/port/database/
    username/password for a database connection, or a REST auth header
    value) used by Data Source credentials. At least one secret field must
    be provided so the store never holds an empty, useless credential.
    """
    extra = {k: v for k, v in (extra or {}).items() if v is not None and str(v).strip() != ""}
    if (not api_key or not api_key.strip()) and not extra:
        raise ValueError("At least one secret field (API key or connection detail) is required")

    credential_id = f"cred_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    fernet = _get_fernet()
    token = fernet.encrypt(api_key.strip().encode()).decode() if api_key and api_key.strip() else ""
    extra_token = fernet.encrypt(json.dumps(extra).encode()).decode() if extra else ""
    record = {
        "id": credential_id,
        "name": name.strip() or f"{provider.title()} credential",
        "provider": provider.strip().lower(),
        "api_key": token,
        "api_url": api_url or "",
        "extra": extra_token,
        "extra_keys": sorted(extra.keys()),
        "created_at": now,
        "updated_at": now,
    }
    with _lock:
        data = _read()
        data.append(record)
        _write(data)
    return {k: v for k, v in record.items() if k not in {"api_key", "api_url", "extra"}}


def get_credential(credential_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        for item in _read():
            if item.get("id") != credential_id:
                continue
            fernet = _get_fernet()
            try:
                api_key = (
                    fernet.decrypt(item["api_key"].encode()).decode()
                    if item.get("api_key") else ""
                )
                extra: Dict[str, str] = {}
                if item.get("extra"):
                    extra = json.loads(fernet.decrypt(item["extra"].encode()).decode())
            except Exception as exc:
                raise RuntimeError("Unable to decrypt credential. Check CREDENTIAL_ENCRYPTION_KEY.") from exc
            return {
                "id": item["id"],
                "name": item.get("name", item["id"]),
                "provider": item.get("provider", "custom"),
                "api_key": api_key,
                "api_url": item.get("api_url", ""),
                "extra": extra,
            }
    return None


def find_whatsapp_channel(phone_number_id: str) -> Optional[Dict[str, Any]]:
    """Find the WhatsApp credential bound to a Cloud API ``phone_number_id``.

    Used by the inbound webhook to figure out which flow should answer a
    message that just arrived on a given WhatsApp Business number, and
    which access token to reply with. Returns ``None`` if no ``provider:
    "whatsapp"`` credential has a matching ``extra.phone_number_id``.
    """
    with _lock:
        fernet = _get_fernet()
        for item in _read():
            if item.get("provider") != "whatsapp":
                continue
            try:
                extra = (
                    json.loads(fernet.decrypt(item["extra"].encode()).decode())
                    if item.get("extra") else {}
                )
            except Exception:
                continue
            if extra.get("phone_number_id") != phone_number_id:
                continue
            try:
                api_key = (
                    fernet.decrypt(item["api_key"].encode()).decode()
                    if item.get("api_key") else ""
                )
            except Exception:
                continue
            return {
                "credential_id": item["id"],
                "flow_id": extra.get("flow_id"),
                "access_token": api_key,
                "phone_number_id": extra.get("phone_number_id"),
                "verify_token": extra.get("verify_token"),
            }
    return None


def find_whatsapp_channel_by_verify_token(verify_token: str) -> Optional[Dict[str, Any]]:
    """Find a WhatsApp credential by its webhook verify token (used for Meta's GET handshake)."""
    if not verify_token:
        return None
    with _lock:
        fernet = _get_fernet()
        for item in _read():
            if item.get("provider") != "whatsapp":
                continue
            try:
                extra = (
                    json.loads(fernet.decrypt(item["extra"].encode()).decode())
                    if item.get("extra") else {}
                )
            except Exception:
                continue
            if extra.get("verify_token") and extra.get("verify_token") == verify_token:
                return {"credential_id": item["id"], "flow_id": extra.get("flow_id")}
    return None




def find_360dialog_channel() -> Optional[Dict[str, Any]]:
    """Return the saved 360dialog credential bound to a reply flow."""
    with _lock:
        fernet = _get_fernet()
        for item in _read():
            if item.get("provider") != "360dialog":
                continue
            try:
                extra = (
                    json.loads(fernet.decrypt(item["extra"].encode()).decode())
                    if item.get("extra") else {}
                )
                api_key = (
                    fernet.decrypt(item["api_key"].encode()).decode()
                    if item.get("api_key") else ""
                )
            except Exception:
                continue
            if not extra.get("flow_id"):
                continue
            return {
                "credential_id": item["id"],
                "flow_id": extra.get("flow_id"),
                "api_key": api_key,
                "environment": extra.get("environment") or "sandbox",
            }
    return None


def delete_credential(credential_id: str) -> bool:
    """Delete a saved credential by ID.

    Returns True when a credential was removed, or False when the ID was not
    present. This mirrors the contract used by DELETE /credentials/{id}.
    """
    with _lock:
        data = _read()
        new_data = [item for item in data if item.get("id") != credential_id]
        if len(new_data) == len(data):
            return False
        _write(new_data)
        return True
