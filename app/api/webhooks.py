"""Inbound WhatsApp webhook.

Lets a saved flow act as a full WhatsApp bot: point Meta's WhatsApp Cloud
API webhook at this server, bind a WhatsApp credential (provider
"whatsapp") to a flow via ``extra.flow_id``, and incoming messages on that
number are run through the normal flow engine and answered automatically.

Setup, once a WhatsApp credential exists (POST /credentials with
provider="whatsapp", api_key=<access token>, extra={"phone_number_id": "...",
"verify_token": "...", "flow_id": "..."}):

  1. In the Meta App dashboard, set the webhook callback URL to
     ``https://<your-domain>/webhooks/whatsapp`` and the verify token to the
     same value stored in the credential's ``extra.verify_token``.
  2. Subscribe the webhook to the ``messages`` field.

Nothing else is required — this module resolves the right flow purely from
the ``phone_number_id`` Meta sends in each payload.
"""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from app.storage.credentials import (
    find_whatsapp_channel,
    find_whatsapp_channel_by_verify_token,
    find_360dialog_channel,
)
from app.nodes.whatsapp import send_whatsapp_message, send_360dialog_message

logger = logging.getLogger("flow_engine.webhooks.whatsapp")

router = APIRouter()


@router.get("/webhooks/whatsapp")
async def verify_whatsapp_webhook(request: Request) -> Response:
    """Meta's one-time webhook verification handshake."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge") or ""

    if mode == "subscribe" and find_whatsapp_channel_by_verify_token(token or ""):
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Webhook verification failed: verify token did not match.")


@router.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Receive an inbound WhatsApp message, run it through the bound flow, and reply.

    Always returns 200 quickly: Meta retries (and eventually disables) a
    webhook that responds with errors, so failures are logged, not raised.
    """
    # Local import: avoids a circular import at module load time, since
    # app.api.routes imports things that (indirectly) import this package.
    from app.api.routes import chat, ChatRequest

    try:
        for entry in payload.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value") or {}
                phone_number_id = (value.get("metadata") or {}).get("phone_number_id")
                messages = value.get("messages") or []
                if not phone_number_id or not messages:
                    continue

                channel = find_whatsapp_channel(phone_number_id)
                if not channel or not channel.get("flow_id"):
                    logger.warning(
                        "Received WhatsApp message for phone_number_id=%s but no credential "
                        "with a matching extra.phone_number_id + extra.flow_id was found.",
                        phone_number_id,
                    )
                    continue

                for message in messages:
                    sender = message.get("from")
                    text = ((message.get("text") or {}).get("body") or "").strip()
                    if not sender:
                        continue

                    conversation_id = f"whatsapp:{phone_number_id}:{sender}"

                    try:
                        chat_response = await chat(
                            ChatRequest(
                                conversation_id=conversation_id,
                                flow_id=channel["flow_id"],
                                message=text,
                            )
                        )
                    except Exception:
                        logger.exception(
                            "Flow '%s' failed to process WhatsApp message from %s",
                            channel["flow_id"], sender,
                        )
                        continue

                    if chat_response.response:
                        try:
                            send_whatsapp_message(
                                phone_number_id,
                                channel["access_token"],
                                sender,
                                chat_response.response,
                            )
                        except Exception:
                            logger.exception("Failed to send WhatsApp reply to %s", sender)
    except Exception:
        logger.exception("Failed to process WhatsApp webhook payload: %r", payload)

    return {"status": "received"}



@router.post("/webhooks/360dialog/whatsapp")
async def receive_360dialog_whatsapp_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Receive 360dialog inbound WhatsApp events and route text messages through the bound flow."""
    from app.api.routes import chat, ChatRequest

    try:
        channel = find_360dialog_channel()
        if not channel or not channel.get("flow_id"):
            logger.warning("Received 360dialog webhook but no 360dialog credential with extra.flow_id was found.")
            return {"status": "received"}

        for entry in payload.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value") or {}
                for message in value.get("messages", []) or []:
                    sender = str(message.get("from") or "").strip()
                    text = str(((message.get("text") or {}).get("body") or "")).strip()
                    if not sender or not text:
                        continue

                    conversation_id = f"360dialog:{channel['credential_id']}:{sender}"
                    try:
                        chat_response = await chat(ChatRequest(
                            conversation_id=conversation_id,
                            flow_id=channel["flow_id"],
                            message=text,
                        ))
                    except Exception:
                        logger.exception("Flow '%s' failed to process 360dialog message from %s", channel["flow_id"], sender)
                        continue

                    if chat_response.response:
                        try:
                            send_360dialog_message(
                                str(channel.get("api_key") or ""),
                                sender,
                                chat_response.response,
                                str(channel.get("environment") or "sandbox"),
                            )
                        except Exception:
                            logger.exception("Failed to send 360dialog reply to %s", sender)
    except Exception:
        logger.exception("Failed to process 360dialog webhook payload: %r", payload)

    return {"status": "received"}
