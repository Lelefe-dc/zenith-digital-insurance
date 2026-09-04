from __future__ import annotations
import hashlib
import hmac
import logging
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from .config import get_settings
from .database import get_db
from .engine import start_session, handle_message
from .models import ConversationSession

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp"])
log = logging.getLogger("zenith.whatsapp")
settings = get_settings()


def _valid_signature(body: bytes, signature: str | None) -> bool:
    if not settings.whatsapp_app_secret:
        return True
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(settings.whatsapp_app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.split("=", 1)[1], expected)


async def _send_text(to: str, text: str) -> None:
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        log.info("WhatsApp outbound not configured. Would send to %s: %s", to, text)
        return
    url = f"https://graph.facebook.com/{settings.whatsapp_graph_version}/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()


@router.get("")
def verify_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token and hub_challenge:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def inbound_whatsapp(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    db: Session = Depends(get_db),
):
    body = await request.body()
    if not _valid_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")
    payload = await request.json()
    try:
        change = payload["entry"][0]["changes"][0]["value"]
        messages = change.get("messages") or []
    except (KeyError, IndexError, TypeError):
        return {"status": "ignored"}
    for msg in messages:
        from_number = msg.get("from")
        if not from_number:
            continue
        text = (msg.get("text") or {}).get("body", "")
        if not text:
            await _send_text(from_number, "Please send a text message, or use the browser assistant for file upload.")
            continue
        session = (
            db.query(ConversationSession)
            .filter(ConversationSession.channel == "whatsapp", ConversationSession.channel_user_id == from_number, ConversationSession.status == "active")
            .order_by(ConversationSession.created_at.desc())
            .first()
        )
        if not session:
            started = start_session(db, user_id=from_number, channel="whatsapp")
            for m in started.messages:
                await _send_text(from_number, m)
            # Process the inbound greeting only if it looks like a language choice.
            if text.strip().lower() in {"1", "2", "english", "sesotho"}:
                result = handle_message(db, started.session_id, text)
                for m in result.messages:
                    await _send_text(from_number, m)
        else:
            result = handle_message(db, session.id, text)
            for m in result.messages:
                await _send_text(from_number, m)
            if result.options:
                await _send_text(from_number, "\n".join(o.label for o in result.options))
    return {"status": "accepted"}
