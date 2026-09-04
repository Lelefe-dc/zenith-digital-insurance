import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.core_models import ClaimSettlement, PolicyTransaction, UnderwritingQuote
from app.core_insurance import (
    ClaimActivityRequest,
    ClaimSettlementRequest,
    KYCUpdateRequest,
    PolicyActionRequest,
    QuoteConvertRequest,
    QuoteDecisionRequest,
    QuoteRateRequest,
    add_claim_activity,
    add_claim_settlement,
    convert_quote,
    customer_360,
    decide_quote,
    policy_action,
    rate_quote,
    update_kyc,
)
from app.management_models import Customer, InsuranceProduct, StaffUser
from app.models import Claim, Policy
from app.seed import seed_demo_data


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    seed_demo_data(db)
    admin = db.query(StaffUser).filter(StaffUser.role == "Administrator").first()
    return db, admin


def test_rate_approve_convert_and_policy_lifecycle():
    db, admin = make_db()
    customer = db.query(Customer).filter(Customer.customer_number == "CUS-2026-000001").first()
    product = db.query(InsuranceProduct).filter(InsuranceProduct.code == "MOTOR").first()

    quote = rate_quote(
        QuoteRateRequest(
            customer_id=customer.id,
            product_id=product.id,
            sum_insured=300000,
            excess_amount=2500,
            risk={"usage": "private", "claims_count": 0, "security_features": True},
        ),
        admin,
        db,
    )
    assert quote["reference"].startswith("QUO-")
    assert quote["total_premium"] > 0

    decide_quote(quote["id"], QuoteDecisionRequest(status="Approved", decision_notes="Test approval"), admin, db)
    converted = convert_quote(
        quote["id"],
        QuoteConvertRequest(effective_date=date(2026, 9, 4), expiry_date=date(2027, 9, 3)),
        admin,
        db,
    )
    policy = db.query(Policy).filter(Policy.id == converted["policy_id"]).first()
    assert policy.status == "Active"
    assert db.query(UnderwritingQuote).filter(UnderwritingQuote.id == quote["id"]).first().status == "Converted"
    assert db.query(PolicyTransaction).filter(PolicyTransaction.policy_id == policy.id, PolicyTransaction.transaction_type == "Issue").count() == 1

    policy_action(policy.id, PolicyActionRequest(action="Suspend", reason="Test hold"), admin, db)
    assert policy.status == "Suspended"
    policy_action(policy.id, PolicyActionRequest(action="Reinstate", reason="Test reinstate"), admin, db)
    assert policy.status == "Active"


def test_claim_activity_settlement_and_customer_360():
    db, admin = make_db()
    customer = db.query(Customer).filter(Customer.customer_number == "CUS-2026-000001").first()
    claim = db.query(Claim).filter(Claim.policy_number == "ZEN-100001").first()
    if not claim:
        claim = Claim(
            reference="ZC-TEST-001",
            session_id="test-session",
            policy_number="ZEN-100001",
            loss_date=date(2026, 9, 1),
            description="Test collision",
            location="Maseru",
            estimated_damage=5000,
            contact="58000001",
            status="Registered",
        )
        db.add(claim)
        db.commit()
        db.refresh(claim)

    add_claim_activity(claim.id, ClaimActivityRequest(activity_type="Assessment", status="Assessing", notes="Assigned for assessment"), admin, db)
    settlement = add_claim_settlement(claim.id, ClaimSettlementRequest(amount=1000, status="Paid", payment_reference="BANK-001"), admin, db)
    assert settlement["status"] == "Paid"
    assert db.query(ClaimSettlement).filter(ClaimSettlement.claim_id == claim.id).count() == 1

    kyc = update_kyc(
        customer.id,
        KYCUpdateRequest(
            verification_status="Verified",
            identity_type="National ID",
            identity_number="DEMO-900101",
            proof_of_address_status="Verified",
            pep_status="Clear",
            sanctions_status="Clear",
            risk_rating="Low",
        ),
        admin,
        db,
    )
    assert kyc["verification_status"] == "Verified"

    view = customer_360(customer.id, admin, db)
    assert view["customer"]["customer_number"] == customer.customer_number
    assert view["summary"]["policy_count"] >= 1
    assert view["summary"]["claim_count"] >= 1
