from __future__ import annotations
import mimetypes
import os
import re
import secrets
from pathlib import Path
from fastapi import FastAPI, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session
from .config import get_settings
from .database import Base, engine, get_db, SessionLocal
from .engine import start_session, handle_message
from .models import Lead, Claim, ClaimAttachment, AgentTicket, ConversationSession, AuditEvent
from .schemas import ChatStartRequest, ChatMessageRequest, ChatResponse
from .seed import seed_demo_data
from .whatsapp import router as whatsapp_router

settings = get_settings()
Base.metadata.create_all(bind=engine)
with SessionLocal() as _db:
    seed_demo_data(_db)

app = FastAPI(title=settings.app_name, version="1.0.0", description="Zenith Horizon Insurance Company Limited digital insurance assistant")
app.include_router(whatsapp_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.post("/api/v1/chat/start", response_model=ChatResponse)
def chat_start(payload: ChatStartRequest, db: Session = Depends(get_db)):
    return start_session(db, payload.user_id, payload.channel)


@app.post("/api/v1/chat/message", response_model=ChatResponse)
def chat_message(payload: ChatMessageRequest, db: Session = Depends(get_db)):
    try:
        return handle_message(db, payload.session_id, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def _admin_guard(x_admin_token: str | None = Header(None)):
    if not secrets.compare_digest(x_admin_token or "", settings.admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


@app.get("/api/v1/admin/dashboard", dependencies=[Depends(_admin_guard)])
def dashboard(db: Session = Depends(get_db)):
    counts = {
        "sessions": db.query(func.count(ConversationSession.id)).scalar() or 0,
        "leads": db.query(func.count(Lead.id)).scalar() or 0,
        "claims": db.query(func.count(Claim.id)).scalar() or 0,
        "tickets": db.query(func.count(AgentTicket.id)).scalar() or 0,
    }
    recent_leads = db.query(Lead).order_by(Lead.created_at.desc()).limit(10).all()
    recent_claims = db.query(Claim).order_by(Claim.created_at.desc()).limit(10).all()
    recent_tickets = db.query(AgentTicket).order_by(AgentTicket.created_at.desc()).limit(10).all()
    return {
        "counts": counts,
        "leads": [{"reference": x.reference, "name": x.name, "mobile": x.mobile, "product": x.product, "status": x.status, "created_at": x.created_at.isoformat()} for x in recent_leads],
        "claims": [{"reference": x.reference, "policy_number": x.policy_number, "loss_date": x.loss_date.isoformat(), "location": x.location, "status": x.status, "created_at": x.created_at.isoformat()} for x in recent_claims],
        "tickets": [{"reference": x.reference, "queue": x.queue, "reason": x.reason, "status": x.status, "created_at": x.created_at.isoformat()} for x in recent_tickets],
    }


@app.get("/api/v1/admin/audit", dependencies=[Depends(_admin_guard)])
def audit(limit: int = 100, db: Session = Depends(get_db)):
    limit = min(max(limit, 1), 500)
    rows = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit).all()
    return [{"id": x.id, "session_id": x.session_id, "event_type": x.event_type, "payload": x.payload_json, "created_at": x.created_at.isoformat()} for x in rows]


ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


@app.post("/api/v1/claims/{claim_reference}/attachments")
async def upload_claim_attachment(claim_reference: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    claim = db.query(Claim).filter(Claim.reference == claim_reference).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    if mime not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail="Only JPG, PNG, WEBP and PDF files are allowed")
    data = await file.read((settings.max_upload_mb * 1024 * 1024) + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB limit")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename or "attachment")
    stored_name = f"{claim_reference}_{secrets.token_hex(6)}_{safe_name}"
    path = Path(settings.upload_dir) / stored_name
    path.write_bytes(data)
    att = ClaimAttachment(claim_id=claim.id, filename=safe_name, stored_path=str(path), mime_type=mime, size_bytes=len(data))
    db.add(att)
    db.add(AuditEvent(session_id=claim.session_id, event_type="claim_attachment_uploaded", payload_json=f'{{"claim_reference":"{claim_reference}","filename":"{safe_name}"}}'))
    db.commit()
    return {"status": "uploaded", "claim_reference": claim_reference, "filename": safe_name, "size_bytes": len(data)}
