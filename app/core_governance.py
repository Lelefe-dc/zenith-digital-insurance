from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .core_models import ApprovalRequest, DocumentProfile
from .database import get_db
from .management import MANAGER_ROLES, _audit, _iso, _require, current_user
from .management_models import ManagedDocument, StaffUser, SystemSetting

router = APIRouter(prefix="/api/v1/management/core", tags=["Core governance"])


class ApprovalCreate(BaseModel):
    workflow: str = Field(min_length=2, max_length=80)
    entity_type: str = Field(min_length=2, max_length=40)
    entity_id: int
    stage: str = Field(default="Review", min_length=2, max_length=60)
    amount: float | None = Field(default=None, ge=0)
    assigned_to_id: int | None = None
    reason: str | None = Field(default=None, max_length=5000)


class ApprovalDecision(BaseModel):
    status: str = Field(pattern="^(Approved|Rejected|Returned|Cancelled)$")
    decision_notes: str | None = Field(default=None, max_length=5000)


class DocumentProfileUpdate(BaseModel):
    category: str = Field(default="General", min_length=2, max_length=80)
    document_status: str = Field(default="Current", pattern="^(Current|Superseded|Expired|Rejected|Archived)$")
    expiry_date: date | None = None
    supersedes_document_id: int | None = None
    notes: str | None = Field(default=None, max_length=5000)


def _setting_bool(db: Session, key: str, default: bool = True) -> bool:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not row:
        return default
    return str(row.value).strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _approval_dict(row: ApprovalRequest, requester: StaffUser | None = None, assignee: StaffUser | None = None, decider: StaffUser | None = None) -> dict:
    return {
        "id": row.id,
        "reference": row.reference,
        "workflow": row.workflow,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "stage": row.stage,
        "status": row.status,
        "amount": row.amount,
        "requested_by_id": row.requested_by_id,
        "requested_by": requester.full_name if requester else None,
        "assigned_to_id": row.assigned_to_id,
        "assigned_to": assignee.full_name if assignee else None,
        "decided_by_id": row.decided_by_id,
        "decided_by": decider.full_name if decider else None,
        "reason": row.reason,
        "decision_notes": row.decision_notes,
        "requested_at": _iso(row.requested_at),
        "decided_at": _iso(row.decided_at),
    }


@router.post("/approvals")
def create_approval(payload: ApprovalCreate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    if payload.assigned_to_id:
        assignee = db.query(StaffUser).filter(StaffUser.id == payload.assigned_to_id, StaffUser.active.is_(True)).first()
        if not assignee:
            raise HTTPException(status_code=404, detail="Assigned approver not found or inactive")
    row = ApprovalRequest(
        reference=f"APR-{datetime.utcnow():%Y%m%d}-{secrets.token_hex(3).upper()}",
        workflow=payload.workflow,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        stage=payload.stage,
        status="Pending",
        amount=payload.amount,
        requested_by_id=user.id,
        assigned_to_id=payload.assigned_to_id,
        reason=payload.reason,
    )
    db.add(row)
    db.flush()
    _audit(db, user, "approval.requested", {"approval_id": row.id, "reference": row.reference, "workflow": row.workflow, "entity_type": row.entity_type, "entity_id": row.entity_id})
    db.commit()
    db.refresh(row)
    return _approval_dict(row, requester=user)


@router.get("/approvals")
def list_approvals(
    status: str | None = None,
    workflow: str | None = None,
    assigned_to_me: bool = False,
    limit: int = Query(250, ge=1, le=500),
    user: StaffUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    requester = StaffUser
    rows = db.query(ApprovalRequest).order_by(ApprovalRequest.requested_at.desc())
    if status:
        rows = rows.filter(ApprovalRequest.status == status)
    if workflow:
        rows = rows.filter(ApprovalRequest.workflow == workflow)
    if assigned_to_me:
        rows = rows.filter(ApprovalRequest.assigned_to_id == user.id)
    out = []
    for row in rows.limit(limit).all():
        req = db.query(StaffUser).filter(StaffUser.id == row.requested_by_id).first()
        assignee = db.query(StaffUser).filter(StaffUser.id == row.assigned_to_id).first() if row.assigned_to_id else None
        decider = db.query(StaffUser).filter(StaffUser.id == row.decided_by_id).first() if row.decided_by_id else None
        out.append(_approval_dict(row, req, assignee, decider))
    return out


@router.patch("/approvals/{approval_id}/decision")
def decide_approval(approval_id: int, payload: ApprovalDecision, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, MANAGER_ROLES | {"Underwriter", "Claims", "Finance"})
    row = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if row.status not in {"Pending", "Returned"}:
        raise HTTPException(status_code=409, detail=f"Approval is already {row.status}")
    if row.assigned_to_id and row.assigned_to_id != user.id and user.role not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="This approval is assigned to another staff member")
    if payload.status in {"Approved", "Rejected"} and _setting_bool(db, "approvals.enforce_maker_checker", True) and row.requested_by_id == user.id:
        raise HTTPException(status_code=409, detail="Maker/checker control prevents approving your own request")
    row.status = payload.status
    row.decision_notes = payload.decision_notes
    row.decided_by_id = user.id
    row.decided_at = datetime.utcnow()
    _audit(db, user, "approval.decided", {"approval_id": row.id, "reference": row.reference, "status": row.status})
    db.commit()
    return {"id": row.id, "reference": row.reference, "status": row.status, "decided_at": _iso(row.decided_at)}


def _checksum(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _document_dict(doc: ManagedDocument, profile: DocumentProfile | None) -> dict:
    return {
        "id": doc.id,
        "entity_type": doc.entity_type,
        "entity_id": doc.entity_id,
        "filename": doc.filename,
        "mime_type": doc.mime_type,
        "size_bytes": doc.size_bytes,
        "created_at": _iso(doc.created_at),
        "category": profile.category if profile else "Unclassified",
        "document_status": profile.document_status if profile else "Current",
        "version": profile.version if profile else 1,
        "expiry_date": _iso(profile.expiry_date) if profile else None,
        "checksum_sha256": profile.checksum_sha256 if profile else None,
        "supersedes_document_id": profile.supersedes_document_id if profile else None,
        "notes": profile.notes if profile else None,
    }


@router.put("/documents/{document_id}/profile")
def update_document_profile(document_id: int, payload: DocumentProfileUpdate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    doc = db.query(ManagedDocument).filter(ManagedDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Managed document not found")
    superseded_profile = None
    if payload.supersedes_document_id:
        old_doc = db.query(ManagedDocument).filter(ManagedDocument.id == payload.supersedes_document_id).first()
        if not old_doc:
            raise HTTPException(status_code=404, detail="Superseded document not found")
        if old_doc.entity_type != doc.entity_type or old_doc.entity_id != doc.entity_id:
            raise HTTPException(status_code=409, detail="Document versions must belong to the same record")
        superseded_profile = db.query(DocumentProfile).filter(DocumentProfile.document_id == old_doc.id).first()
    row = db.query(DocumentProfile).filter(DocumentProfile.document_id == doc.id).first()
    version = (superseded_profile.version + 1) if superseded_profile else (row.version if row else 1)
    if not row:
        row = DocumentProfile(document_id=doc.id)
        db.add(row)
    row.category = payload.category
    row.document_status = payload.document_status
    row.version = version
    row.expiry_date = payload.expiry_date
    row.checksum_sha256 = _checksum(Path(doc.stored_path))
    row.supersedes_document_id = payload.supersedes_document_id
    row.notes = payload.notes
    row.updated_by_id = user.id
    if superseded_profile and superseded_profile.document_status == "Current":
        superseded_profile.document_status = "Superseded"
    _audit(db, user, "document.profiled", {"document_id": doc.id, "category": row.category, "version": row.version, "status": row.document_status})
    db.commit()
    db.refresh(row)
    return _document_dict(doc, row)


@router.get("/documents")
def governed_documents(
    entity_type: str,
    entity_id: int,
    current_only: bool = False,
    user: StaffUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ManagedDocument, DocumentProfile)
        .outerjoin(DocumentProfile, DocumentProfile.document_id == ManagedDocument.id)
        .filter(ManagedDocument.entity_type == entity_type, ManagedDocument.entity_id == entity_id)
        .order_by(ManagedDocument.created_at.desc())
        .all()
    )
    out = [_document_dict(doc, profile) for doc, profile in rows]
    if current_only:
        out = [x for x in out if x["document_status"] == "Current"]
    return out
