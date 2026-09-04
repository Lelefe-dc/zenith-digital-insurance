from __future__ import annotations

import json
import secrets
import uuid
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, or_
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, get_db
from .management import ADMIN_ROLES, CLAIMS_ROLES, MANAGER_ROLES, _audit, _iso, _require, current_user
from .management_models import Customer, ManagedDocument, StaffUser
from .models import AgentTicket, AuditEvent, Claim, Lead, Policy
from .security import hash_password, verify_password

router = APIRouter(prefix="/api/v1/management", tags=["Management workflows"])


class ServiceTicketProfile(Base):
    __tablename__ = "service_ticket_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("agent_tickets.id"), unique=True, index=True)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(20), default="Normal", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)


class ManualLeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    mobile: str = Field(min_length=5, max_length=40)
    product: str = Field(min_length=2, max_length=80)
    consent: bool = True
    status: str = "New"


class ManualClaimCreate(BaseModel):
    policy_number: str = Field(min_length=3, max_length=50)
    loss_date: date
    description: str = Field(min_length=5, max_length=5000)
    location: str = Field(min_length=2, max_length=220)
    estimated_damage: float | None = Field(default=None, ge=0)
    contact: str = Field(min_length=5, max_length=60)
    status: str = "Registered"


class TicketUpdate(BaseModel):
    status: str | None = None
    queue: str | None = None
    priority: str | None = None
    assigned_to_id: int | None = None
    notes: str | None = None


@router.post("/auth/change-password")
def change_password(payload: PasswordChange, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    _audit(db, user, "password.changed", {})
    db.commit()
    return {"status": "ok"}


@router.post("/leads")
def create_manual_lead(payload: ManualLeadCreate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    reference = f"ZQ-{datetime.utcnow():%Y%m%d}-{secrets.token_hex(3).upper()}"
    row = Lead(
        reference=reference,
        session_id=str(uuid.uuid4()),
        name=payload.name,
        mobile=payload.mobile,
        product=payload.product,
        risk_json="{}",
        consent=payload.consent,
        status=payload.status,
        source="management",
    )
    db.add(row); db.flush()
    _audit(db, user, "lead.created", {"lead_id": row.id, "reference": row.reference, "source": "management"})
    db.commit(); db.refresh(row)
    return {"id": row.id, "reference": row.reference, "status": row.status}


@router.post("/claims")
def create_manual_claim(payload: ManualClaimCreate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, CLAIMS_ROLES)
    policy = db.query(Policy).filter(Policy.policy_number == payload.policy_number.strip().upper()).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    reference = f"ZC-{datetime.utcnow():%Y%m%d}-{secrets.token_hex(3).upper()}"
    row = Claim(reference=reference, session_id=str(uuid.uuid4()), **{**payload.model_dump(), "policy_number": policy.policy_number})
    db.add(row); db.flush()
    _audit(db, user, "claim.created", {"claim_id": row.id, "reference": row.reference, "source": "management"})
    db.commit(); db.refresh(row)
    return {"id": row.id, "reference": row.reference, "status": row.status}


@router.get("/tickets")
def list_tickets(status: str | None = None, limit: int = Query(250, ge=1, le=500), user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    query = (
        db.query(AgentTicket, ServiceTicketProfile, StaffUser)
        .outerjoin(ServiceTicketProfile, ServiceTicketProfile.ticket_id == AgentTicket.id)
        .outerjoin(StaffUser, StaffUser.id == ServiceTicketProfile.assigned_to_id)
    )
    if status:
        query = query.filter(AgentTicket.status == status)
    rows = query.order_by(AgentTicket.created_at.desc()).limit(limit).all()
    return [{
        "id": ticket.id,
        "reference": ticket.reference,
        "reason": ticket.reason,
        "queue": ticket.queue,
        "language": ticket.language,
        "status": ticket.status,
        "priority": profile.priority if profile else "Normal",
        "assigned_to_id": profile.assigned_to_id if profile else None,
        "assigned_to": staff.full_name if staff else None,
        "notes": profile.notes if profile else None,
        "created_at": _iso(ticket.created_at),
    } for ticket, profile, staff in rows]


@router.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: int, payload: TicketUpdate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    ticket = db.query(AgentTicket).filter(AgentTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Service ticket not found")
    profile = db.query(ServiceTicketProfile).filter(ServiceTicketProfile.ticket_id == ticket.id).first()
    if not profile:
        profile = ServiceTicketProfile(ticket_id=ticket.id)
        db.add(profile)
    values = payload.model_dump(exclude_unset=True)
    if "status" in values: ticket.status = values.pop("status")
    if "queue" in values: ticket.queue = values.pop("queue")
    for key, value in values.items(): setattr(profile, key, value)
    _audit(db, user, "ticket.updated", {"ticket_id": ticket.id, "reference": ticket.reference, "status": ticket.status})
    db.commit()
    return {"status": "ok", "ticket_id": ticket.id, "ticket_status": ticket.status}


@router.get("/audit")
def audit_trail(
    q: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    user: StaffUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    _require(user, MANAGER_ROLES | {"Claims", "Finance", "Underwriter"})
    query = db.query(AuditEvent)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(AuditEvent.event_type.ilike(like), AuditEvent.payload_json.ilike(like)))
    rows = query.order_by(AuditEvent.created_at.desc()).limit(limit).all()
    out = []
    for row in rows:
        try: payload = json.loads(row.payload_json or "{}")
        except json.JSONDecodeError: payload = {"raw": row.payload_json}
        out.append({"id": row.id, "event_type": row.event_type, "session_id": row.session_id, "payload": payload, "created_at": _iso(row.created_at)})
    return out


@router.get("/documents/{document_id}/download")
def download_document(document_id: int, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    row = db.query(ManagedDocument).filter(ManagedDocument.id == document_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    path = Path(row.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document file is no longer available")
    return FileResponse(path, media_type=row.mime_type, filename=row.filename)


@router.get("/search")
def global_search(q: str = Query(min_length=2, max_length=100), user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    like = f"%{q.strip()}%"
    customers = db.query(Customer).filter(or_(Customer.full_name.ilike(like), Customer.customer_number.ilike(like), Customer.mobile.ilike(like))).limit(6).all()
    policies = db.query(Policy).filter(or_(Policy.policy_number.ilike(like), Policy.holder_name.ilike(like))).limit(6).all()
    claims = db.query(Claim).filter(or_(Claim.reference.ilike(like), Claim.policy_number.ilike(like))).limit(6).all()
    leads = db.query(Lead).filter(or_(Lead.reference.ilike(like), Lead.name.ilike(like), Lead.mobile.ilike(like))).limit(6).all()
    return {
        "customers": [{"id": x.id, "reference": x.customer_number, "label": x.full_name, "detail": x.mobile} for x in customers],
        "policies": [{"id": x.id, "reference": x.policy_number, "label": x.holder_name, "detail": x.product} for x in policies],
        "claims": [{"id": x.id, "reference": x.reference, "label": x.policy_number, "detail": x.status} for x in claims],
        "leads": [{"id": x.id, "reference": x.reference, "label": x.name, "detail": x.status} for x in leads],
    }
