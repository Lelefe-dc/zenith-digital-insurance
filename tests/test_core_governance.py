import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core_governance import (
    ApprovalCreate,
    ApprovalDecision,
    DocumentProfileUpdate,
    create_approval,
    decide_approval,
    update_document_profile,
)
from app.core_models import ApprovalRequest, DocumentProfile
from app.database import Base
from app.management_models import Customer, ManagedDocument, StaffUser
from app.security import hash_password
from app.seed import seed_demo_data


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    seed_demo_data(db)
    admin = db.query(StaffUser).filter(StaffUser.role == "Administrator").first()
    checker = StaffUser(
        employee_number="EMP-CHECKER",
        full_name="Approval Checker",
        email="checker@zenith.local",
        password_hash=hash_password("checker-password-123"),
        role="Manager",
        department="Management",
        active=True,
    )
    db.add(checker)
    db.commit()
    db.refresh(checker)
    return db, admin, checker


def test_maker_checker_blocks_self_approval_and_allows_checker():
    db, admin, checker = make_db()
    customer = db.query(Customer).first()
    created = create_approval(
        ApprovalCreate(workflow="Compliance Review", entity_type="customer", entity_id=customer.id, reason="Verify KYC"),
        admin,
        db,
    )
    assert created["reference"].startswith("APR-")
    approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == created["id"]).first()
    with pytest.raises(HTTPException) as exc:
        decide_approval(approval.id, ApprovalDecision(status="Approved"), admin, db)
    assert exc.value.status_code == 409

    result = decide_approval(approval.id, ApprovalDecision(status="Approved", decision_notes="Checked"), checker, db)
    assert result["status"] == "Approved"


def test_document_profile_computes_checksum_and_version(tmp_path):
    db, admin, _ = make_db()
    customer = db.query(Customer).first()
    first_path = tmp_path / "identity-v1.txt"
    first_path.write_text("first version", encoding="utf-8")
    first = ManagedDocument(
        entity_type="customer",
        entity_id=customer.id,
        filename="identity-v1.txt",
        stored_path=str(first_path),
        mime_type="text/plain",
        size_bytes=first_path.stat().st_size,
        uploaded_by_id=admin.id,
    )
    db.add(first)
    db.commit()
    db.refresh(first)
    prof1 = update_document_profile(first.id, DocumentProfileUpdate(category="KYC", document_status="Current"), admin, db)
    assert prof1["version"] == 1
    assert len(prof1["checksum_sha256"]) == 64

    second_path = tmp_path / "identity-v2.txt"
    second_path.write_text("second version", encoding="utf-8")
    second = ManagedDocument(
        entity_type="customer",
        entity_id=customer.id,
        filename="identity-v2.txt",
        stored_path=str(second_path),
        mime_type="text/plain",
        size_bytes=second_path.stat().st_size,
        uploaded_by_id=admin.id,
    )
    db.add(second)
    db.commit()
    db.refresh(second)
    prof2 = update_document_profile(second.id, DocumentProfileUpdate(category="KYC", document_status="Current", supersedes_document_id=first.id), admin, db)
    assert prof2["version"] == 2
    old = db.query(DocumentProfile).filter(DocumentProfile.document_id == first.id).first()
    assert old.document_status == "Superseded"
