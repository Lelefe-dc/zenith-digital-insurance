from __future__ import annotations

import mimetypes
import re
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, SessionLocal, engine, get_db
from .engine import handle_message, start_session
from .management import router as management_router
from .models import AuditEvent, Claim, ClaimAttachment
from .schemas import ChatMessageRequest, ChatResponse, ChatStartRequest
from .seed import seed_demo_data
from .whatsapp import router as whatsapp_router

settings = get_settings()
Base.metadata.create_all(bind=engine)
with SessionLocal() as _db:
    seed_demo_data(_db)

app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    description="Zenith Horizon Insurance Company Limited digital insurance and management platform",
)
app.include_router(management_router)
# WhatsApp is kept dormant for the final integration phase. Existing webhook
# compatibility remains available without being part of the management UI.
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
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment, "version": "2.0.0"}


@app.post("/api/v1/chat/start", response_model=ChatResponse)
def chat_start(payload: ChatStartRequest, db: Session = Depends(get_db)):
    return start_session(db, payload.user_id, payload.channel)


@app.post("/api/v1/chat/message", response_model=ChatResponse)
def chat_message(payload: ChatMessageRequest, db: Session = Depends(get_db)):
    try:
        return handle_message(db, payload.session_id, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


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
