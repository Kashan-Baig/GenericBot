"""WhatsApp integrations for Meta Cloud API and 360dialog.

The existing ``whatsapp`` flow node supports two providers:
  * Meta WhatsApp Cloud API (credential provider ``whatsapp``)
  * 360dialog WhatsApp (credential provider ``360dialog``)

Both can send outbound text. Separate inbound webhooks in ``app/api/webhooks.py``
route incoming messages through the normal chat flow and send the response back.
"""
import logging
import os
import re
from typing import Any, Dict

import httpx

from app.nodes.base import BaseNodeExecutor, render_template
from app.storage.credentials import get_credential

logger = logging.getLogger("flow_engine.nodes.whatsapp")
GRAPH_API_VERSION = "v20.0"


def _normalize_number(raw: str) -> str:
    return re.sub(r"[^0-9]", "", str(raw or ""))


def _normalize_e164_number(raw: str) -> str:
    """Return a digits-only E.164 WhatsApp number accepted by 360dialog.

    360dialog expects a country-code-prefixed number. Local numbers such as
    03001234567 are deliberately rejected because guessing the country would
    be unsafe. The API examples use digits only in the JSON ``to`` field.
    """
    number = _normalize_number(raw)
    if not number:
        raise ValueError("WhatsApp recipient number is empty. Enter a number such as +923001234567.")
    if number.startswith("0"):
        raise ValueError(
            f"Invalid WhatsApp number '{raw}'. Use E.164 format with country code, e.g. +923001234567, not a local 03xx number."
        )
    if len(number) < 8 or len(number) > 15:
        raise ValueError(
            f"Invalid WhatsApp number '{raw}'. E.164 numbers must contain 8-15 digits including the country code."
        )
    return number



def send_whatsapp_message(phone_number_id: str, access_token: str, to: str, text: str) -> Dict[str, Any]:
    """Send a plain text message via Meta WhatsApp Cloud API."""
    if not phone_number_id:
        raise ValueError("Missing WhatsApp phone_number_id.")
    if not access_token:
        raise ValueError("Missing WhatsApp access token.")
    to_number = _normalize_number(to)
    if not to_number:
        raise ValueError(f"'{to}' is not a usable WhatsApp phone number after normalization.")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": str(text)[:4096], "preview_url": False},
    }
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text[:1000]
            raise RuntimeError(f"WhatsApp send failed (HTTP {resp.status_code}) at {url}: {detail}")
        return resp.json()


def send_360dialog_message(api_key: str, to: str, text: str, environment: str = "sandbox") -> Dict[str, Any]:
    """Send a WhatsApp text through 360dialog Sandbox or production Messaging API."""
    if not api_key:
        raise ValueError("Missing 360dialog API key.")
    to_number = _normalize_e164_number(to)

    env = str(environment or "sandbox").lower().strip()
    if env == "production":
        url = "https://waba-v2.360dialog.io/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": str(text)[:4096]},
        }
    else:
        url = "https://waba-sandbox.360dialog.io/v1/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {"body": str(text)[:4096]},
        }

    headers = {"D360-API-KEY": api_key, "Content-Type": "application/json"}
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text[:1000]
            raise RuntimeError(f"360dialog WhatsApp send failed (HTTP {resp.status_code}) at {url}: {detail}")
        return resp.json()


class WhatsAppNodeExecutor(BaseNodeExecutor):
    """Send WhatsApp through either Meta Cloud API or 360dialog."""

    def execute(self, node_config: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        config = node_config.get("config") or node_config.get("data") or {}
        variables = state.get("variables", {})

        to_template = str(config.get("to") or node_config.get("to") or "").strip()
        message_template = str(
            config.get("message") or config.get("text")
            or node_config.get("message") or node_config.get("text") or ""
        ).strip()
        message = render_template(message_template, variables)
        if not message:
            raise ValueError("WhatsApp node has no message text.")

        credential_id = config.get("credential_id") or node_config.get("credential_id")
        credential = get_credential(str(credential_id)) if credential_id else None
        credential_extra = (credential or {}).get("extra") or {}
        rendered_to = render_template(to_template, variables) if to_template else ""
        to = str(rendered_to or credential_extra.get("default_to_phone") or "").strip()
        if not to:
            raise ValueError(
                "WhatsApp node has no recipient number. Set 'To' on the node or save a 360dialog Sandbox test WhatsApp number in the credential."
            )
        channel_provider = str(
            config.get("channel_provider")
            or (credential or {}).get("provider")
            or "360dialog"
        ).lower().strip()

        try:
            if channel_provider in {"360dialog", "360_dialog", "dialog360"}:
                api_key = (credential or {}).get("api_key") or os.getenv("D360_API_KEY")
                environment = credential_extra.get("environment") or os.getenv("D360_ENVIRONMENT") or "sandbox"
                send_360dialog_message(str(api_key or ""), to, message, str(environment))
            else:
                phone_number_id = (
                    config.get("phone_number_id") or node_config.get("phone_number_id")
                    or credential_extra.get("phone_number_id") or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
                )
                access_token = (
                    (credential or {}).get("api_key") or config.get("access_token")
                    or os.getenv("WHATSAPP_ACCESS_TOKEN")
                )
                send_whatsapp_message(str(phone_number_id or ""), str(access_token or ""), to, message)
        except Exception as exc:
            logger.exception("WhatsApp node '%s' failed to send to %s: %s", node_config.get("id"), to, exc)
            error_next = node_config.get("error_next_node") or config.get("error_next_node")
            state.setdefault("variables", {})["error"] = {
                "node_id": node_config.get("id"), "message": str(exc), "type": exc.__class__.__name__,
            }
            state["variables"]["error_message"] = str(exc)
            if error_next:
                state["current_node"] = error_next
                state["status"] = "running"
                return state
            raise

        state.setdefault("conversation_history", []).append({
            "role": "assistant", "type": "whatsapp_message", "content": message,
            "to": to, "provider": channel_provider,
        })
        explicit_next = node_config.get("next_node") or config.get("next_node")
        if explicit_next:
            state["current_node"] = explicit_next
        state["status"] = "running"
        return state
