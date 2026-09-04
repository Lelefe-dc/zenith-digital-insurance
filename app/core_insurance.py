from __future__ import annotations

import json
import secrets
from datetime import date, datetime, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .database import get_db
from .management import (
    ADMIN_ROLES,
    CLAIMS_ROLES,
    MANAGER_ROLES,
    UNDERWRITING_ROLES,
    _audit,
    _customer_dict,
    _iso,
    _payment_dict,
    _policy_dict,
    _require,
    current_user,
)
from .management_models import (
    CaseNote,
    ClaimProfile,
    Customer,
    InsuranceProduct,
    ManagedDocument,
    PolicyProfile,
    PremiumPayment,
    StaffUser,
    SystemSetting,
    WorkTask,
)
from .core_models import (
    ClaimActivity,
    ClaimSettlement,
    CustomerKYC,
    Intermediary,
    PolicyIntermediary,
    PolicyTransaction,
    UnderwritingQuote,
)
from .models import Claim, Policy

router = APIRouter(prefix="/api/v1/management/core", tags=["Core insurance"])


class QuoteRateRequest(BaseModel):
    customer_id: int | None = None
    product_id: int
    sum_insured: float = Field(gt=0)
    excess_amount: float = Field(default=0, ge=0)
    risk: dict = Field(default_factory=dict)


class QuoteDecisionRequest(BaseModel):
    status: str = Field(pattern="^(Quoted|Referred|Approved|Declined)$")
    underwriter_id: int | None = None
    decision_notes: str | None = Field(default=None, max_length=5000)


class QuoteConvertRequest(BaseModel):
    effective_date: date
    expiry_date: date | None = None
    payment_frequency: str = "Monthly"
    branch_id: int | None = None
    agent_id: int | None = None
    risk_address: str | None = None


class PolicyActionRequest(BaseModel):
    action: str = Field(pattern="^(Issue|Endorse|Renew|Suspend|Cancel|Reinstate|Expire)$")
    effective_date: date = Field(default_factory=date.today)
    premium: float | None = Field(default=None, gt=0)
    sum_insured: float | None = Field(default=None, ge=0)
    expiry_date: date | None = None
    reason: str | None = Field(default=None, max_length=5000)


class ClaimActivityRequest(BaseModel):
    activity_type: str = Field(min_length=2, max_length=60)
    status: str | None = Field(default=None, max_length=40)
    amount: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=5000)


class ClaimSettlementRequest(BaseModel):
    amount: float = Field(gt=0)
    payment_type: str = Field(default="Settlement", max_length=40)
    status: str = Field(default="Approved", pattern="^(Approved|Paid|Cancelled)$")
    payment_reference: str | None = Field(default=None, max_length=120)
    paid_at: datetime | None = None


class KYCUpdateRequest(BaseModel):
    verification_status: str = "Pending"
    identity_type: str | None = None
    identity_number: str | None = None
    proof_of_address_status: str = "Pending"
    pep_status: str = "Not Assessed"
    sanctions_status: str = "Not Assessed"
    risk_rating: str = "Normal"
    notes: str | None = Field(default=None, max_length=5000)


class IntermediaryCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=180)
    intermediary_type: str = "Agent"
    email: str | None = None
    mobile: str | None = None
    commission_rate: float = Field(default=0, ge=0, le=100)
    active: bool = True


class IntermediaryUpdateRequest(BaseModel):
    name: str | None = None
    intermediary_type: str | None = None
    email: str | None = None
    mobile: str | None = None
    commission_rate: float | None = Field(default=None, ge=0, le=100)
    active: bool | None = None


class PolicyIntermediaryRequest(BaseModel):
    intermediary_id: int
    commission_rate: float | None = Field(default=None, ge=0, le=100)


def _setting_float(db: Session, key: str, default: float) -> float:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not row:
        return default
    try:
        return float(row.value)
    except (TypeError, ValueError):
        return default


def _setting_int(db: Session, key: str, default: int) -> int:
    return int(_setting_float(db, key, float(default)))


def _quote_dict(q: UnderwritingQuote, customer: Customer | None, product: InsuranceProduct | None, underwriter: StaffUser | None = None) -> dict:
    try:
        risk = json.loads(q.risk_json or "{}")
    except json.JSONDecodeError:
        risk = {}
    return {
        "id": q.id,
        "reference": q.reference,
        "customer_id": q.customer_id,
        "customer_name": customer.full_name if customer else None,
        "product_id": q.product_id,
        "product": product.name if product else None,
        "status": q.status,
        "sum_insured": q.sum_insured,
        "excess_amount": q.excess_amount,
        "risk": risk,
        "base_premium": q.base_premium,
        "loading_amount": q.loading_amount,
        "discount_amount": q.discount_amount,
        "tax_amount": q.tax_amount,
        "total_premium": q.total_premium,
        "referral_reason": q.referral_reason,
        "decision_notes": q.decision_notes,
        "underwriter_id": q.underwriter_id,
        "underwriter": underwriter.full_name if underwriter else None,
        "converted_policy_id": q.converted_policy_id,
        "valid_until": _iso(q.valid_until),
        "created_at": _iso(q.created_at),
        "updated_at": _iso(q.updated_at),
        "rating_notice": "Premium is produced by the configurable Zenith rating engine and must be aligned to approved underwriting tariffs before production use.",
    }


def _rate_quote(db: Session, product: InsuranceProduct, payload: QuoteRateRequest) -> tuple[float, float, float, float, float, str | None, str]:
    risk = payload.risk or {}
    base_rate = _setting_float(db, f"rating.{product.code.lower()}.sum_insured_rate", 0.005)
    minimum = max(0.0, float(product.base_premium or 0))
    base = max(minimum, payload.sum_insured * base_rate)

    loading_pct = 0.0
    discount_pct = 0.0
    reasons: list[str] = []

    claims_count = int(risk.get("claims_count") or 0)
    if claims_count == 1:
        loading_pct += _setting_float(db, "rating.claims.one_loading_pct", 10)
        reasons.append("one prior claim")
    elif claims_count >= 2:
        loading_pct += _setting_float(db, "rating.claims.multiple_loading_pct", 25)
        reasons.append("multiple prior claims")

    usage = str(risk.get("usage") or risk.get("use") or "").lower()
    if any(word in usage for word in ("commercial", "business", "taxi", "delivery")):
        loading_pct += _setting_float(db, "rating.commercial_loading_pct", 12)
        reasons.append("commercial usage")

    driver_age = risk.get("driver_age")
    if driver_age is not None:
        try:
            if int(driver_age) < 25:
                loading_pct += _setting_float(db, "rating.young_driver_loading_pct", 15)
                reasons.append("young driver")
        except (TypeError, ValueError):
            pass

    vehicle_age = risk.get("vehicle_age")
    if vehicle_age is not None:
        try:
            if float(vehicle_age) > 10:
                loading_pct += _setting_float(db, "rating.older_vehicle_loading_pct", 10)
                reasons.append("older vehicle")
        except (TypeError, ValueError):
            pass

    if risk.get("security_features") is True:
        discount_pct += _setting_float(db, "rating.security_discount_pct", 5)
    if risk.get("no_claim_bonus") is True:
        discount_pct += _setting_float(db, "rating.no_claim_discount_pct", 5)
    discount_pct = min(discount_pct, _setting_float(db, "rating.maximum_discount_pct", 20))

    loading_amount = base * loading_pct / 100
    discount_amount = base * discount_pct / 100
    subtotal = max(0.0, base + loading_amount - discount_amount)
    tax_pct = _setting_float(db, "rating.tax_pct", 0)
    tax_amount = subtotal * tax_pct / 100
    total = subtotal + tax_amount

    referral_threshold = _setting_float(db, "underwriting.referral_sum_insured", 1_000_000)
    referral_reason = None
    status = "Quoted"
    if payload.sum_insured >= referral_threshold or claims_count >= 2:
        status = "Referred"
        referral_reason = "Manual underwriting referral required"
        if reasons:
            referral_reason += ": " + ", ".join(reasons)

    return tuple(round(v, 2) for v in (base, loading_amount, discount_amount, tax_amount, total)) + (referral_reason, status)


@router.post("/quotes/rate")
def rate_quote(payload: QuoteRateRequest, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, UNDERWRITING_ROLES)
    product = db.query(InsuranceProduct).filter(InsuranceProduct.id == payload.product_id, InsuranceProduct.active.is_(True)).first()
    if not product:
        raise HTTPException(status_code=404, detail="Active product not found")
    customer = None
    if payload.customer_id:
        customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

    base, loading, discount, tax, total, referral_reason, status = _rate_quote(db, product, payload)
    valid_days = max(1, _setting_int(db, "quote.valid_days", 30))
    quote = UnderwritingQuote(
        reference=f"QUO-{datetime.utcnow():%Y%m%d}-{secrets.token_hex(3).upper()}",
        customer_id=payload.customer_id,
        product_id=product.id,
        created_by_id=user.id,
        status=status,
        sum_insured=payload.sum_insured,
        excess_amount=payload.excess_amount,
        risk_json=json.dumps(payload.risk or {}, default=str),
        base_premium=base,
        loading_amount=loading,
        discount_amount=discount,
        tax_amount=tax,
        total_premium=total,
        referral_reason=referral_reason,
        valid_until=date.today() + timedelta(days=valid_days),
    )
    db.add(quote)
    db.flush()
    _audit(db, user, "quote.rated", {"quote_id": quote.id, "reference": quote.reference, "status": quote.status, "total_premium": quote.total_premium})
    db.commit()
    db.refresh(quote)
    return _quote_dict(quote, customer, product)


@router.get("/quotes")
def list_quotes(status: str | None = None, q: str | None = None, limit: int = Query(250, ge=1, le=500), user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    query = (
        db.query(UnderwritingQuote, Customer, InsuranceProduct, StaffUser)
        .outerjoin(Customer, Customer.id == UnderwritingQuote.customer_id)
        .join(InsuranceProduct, InsuranceProduct.id == UnderwritingQuote.product_id)
        .outerjoin(StaffUser, StaffUser.id == UnderwritingQuote.underwriter_id)
    )
    if status:
        query = query.filter(UnderwritingQuote.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(UnderwritingQuote.reference.ilike(like), Customer.full_name.ilike(like), InsuranceProduct.name.ilike(like)))
    return [_quote_dict(*row) for row in query.order_by(UnderwritingQuote.created_at.desc()).limit(limit).all()]


@router.patch("/quotes/{quote_id}/decision")
def decide_quote(quote_id: int, payload: QuoteDecisionRequest, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, UNDERWRITING_ROLES)
    quote = db.query(UnderwritingQuote).filter(UnderwritingQuote.id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quote.converted_policy_id:
        raise HTTPException(status_code=409, detail="Converted quotations cannot be re-decided")
    quote.status = payload.status
    quote.underwriter_id = payload.underwriter_id or user.id
    quote.decision_notes = payload.decision_notes
    _audit(db, user, "quote.decision", {"quote_id": quote.id, "reference": quote.reference, "status": quote.status})
    db.commit()
    return {"status": "ok", "quote_id": quote.id, "quote_status": quote.status}


@router.post("/quotes/{quote_id}/convert")
def convert_quote(quote_id: int, payload: QuoteConvertRequest, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, UNDERWRITING_ROLES)
    quote = db.query(UnderwritingQuote).filter(UnderwritingQuote.id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quote.status != "Approved":
        raise HTTPException(status_code=409, detail="Quotation must be approved before policy conversion")
    if quote.converted_policy_id:
        raise HTTPException(status_code=409, detail="Quotation has already been converted")
    if not quote.customer_id:
        raise HTTPException(status_code=422, detail="Quotation must be linked to a customer before conversion")
    customer = db.query(Customer).filter(Customer.id == quote.customer_id).first()
    product = db.query(InsuranceProduct).filter(InsuranceProduct.id == quote.product_id).first()
    if not customer or not product or not customer.date_of_birth:
        raise HTTPException(status_code=422, detail="Customer, product and customer date of birth are required")

    number = f"ZEN-{datetime.utcnow():%Y}-{secrets.token_hex(4).upper()}"
    policy = Policy(policy_number=number, holder_name=customer.full_name, dob=customer.date_of_birth, status="Active", product=product.name, premium=quote.total_premium, currency=product.currency)
    db.add(policy)
    db.flush()
    profile = PolicyProfile(
        policy_id=policy.id,
        customer_id=customer.id,
        product_id=product.id,
        branch_id=payload.branch_id,
        agent_id=payload.agent_id,
        effective_date=payload.effective_date,
        expiry_date=payload.expiry_date,
        sum_insured=quote.sum_insured,
        payment_frequency=payload.payment_frequency,
        payment_status="Pending",
        risk_address=payload.risk_address,
        notes=f"Converted from quotation {quote.reference}",
    )
    db.add(profile)
    db.add(PolicyTransaction(policy_id=policy.id, transaction_type="Issue", effective_date=payload.effective_date, previous_status=None, new_status="Active", premium_after=policy.premium, sum_insured_after=profile.sum_insured, reason=f"Converted from {quote.reference}", created_by_id=user.id))
    quote.converted_policy_id = policy.id
    quote.status = "Converted"
    _audit(db, user, "quote.converted", {"quote_id": quote.id, "reference": quote.reference, "policy_id": policy.id, "policy_number": number})
    db.commit()
    return {"status": "ok", "quote_reference": quote.reference, "policy_id": policy.id, "policy_number": number}


def _policy_with_profile(db: Session, policy_id: int) -> tuple[Policy, PolicyProfile]:
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    profile = db.query(PolicyProfile).filter(PolicyProfile.policy_id == policy.id).first()
    if not profile:
        raise HTTPException(status_code=409, detail="Policy does not have a management profile")
    return policy, profile


@router.post("/policies/{policy_id}/action")
def policy_action(policy_id: int, payload: PolicyActionRequest, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, UNDERWRITING_ROLES)
    policy, profile = _policy_with_profile(db, policy_id)
    old_status = policy.status
    old_premium = policy.premium
    old_sum = profile.sum_insured
    action = payload.action

    transitions = {
        "Issue": ({"Pending", "Draft"}, "Active"),
        "Suspend": ({"Active"}, "Suspended"),
        "Cancel": ({"Active", "Pending", "Suspended"}, "Cancelled"),
        "Reinstate": ({"Cancelled", "Suspended", "Expired"}, "Active"),
        "Expire": ({"Active", "Suspended"}, "Expired"),
        "Renew": ({"Active", "Expired"}, "Active"),
        "Endorse": ({"Active", "Pending", "Suspended"}, old_status),
    }
    allowed, new_status = transitions[action]
    if old_status not in allowed:
        raise HTTPException(status_code=409, detail=f"Cannot {action.lower()} a policy in {old_status} status")

    if payload.premium is not None:
        policy.premium = payload.premium
    if payload.sum_insured is not None:
        profile.sum_insured = payload.sum_insured
    if payload.expiry_date is not None:
        profile.expiry_date = payload.expiry_date
    elif action == "Renew":
        basis = profile.expiry_date if profile.expiry_date and profile.expiry_date >= payload.effective_date else payload.effective_date
        profile.expiry_date = basis + timedelta(days=365)
    policy.status = new_status

    tx = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=action,
        effective_date=payload.effective_date,
        previous_status=old_status,
        new_status=policy.status,
        premium_before=old_premium,
        premium_after=policy.premium,
        sum_insured_before=old_sum,
        sum_insured_after=profile.sum_insured,
        reason=payload.reason,
        created_by_id=user.id,
    )
    db.add(tx)
    _audit(db, user, "policy.lifecycle", {"policy_id": policy.id, "policy_number": policy.policy_number, "action": action, "old_status": old_status, "new_status": policy.status})
    db.commit()
    return {"status": "ok", "policy_id": policy.id, "policy_number": policy.policy_number, "policy_status": policy.status, "action": action}


@router.get("/policies/{policy_id}/history")
def policy_history(policy_id: int, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    policy, _ = _policy_with_profile(db, policy_id)
    rows = db.query(PolicyTransaction, StaffUser).outerjoin(StaffUser, StaffUser.id == PolicyTransaction.created_by_id).filter(PolicyTransaction.policy_id == policy.id).order_by(PolicyTransaction.created_at.desc()).all()
    return [{
        "id": tx.id,
        "transaction_type": tx.transaction_type,
        "effective_date": _iso(tx.effective_date),
        "previous_status": tx.previous_status,
        "new_status": tx.new_status,
        "premium_before": tx.premium_before,
        "premium_after": tx.premium_after,
        "sum_insured_before": tx.sum_insured_before,
        "sum_insured_after": tx.sum_insured_after,
        "reason": tx.reason,
        "created_by": staff.full_name if staff else None,
        "created_at": _iso(tx.created_at),
    } for tx, staff in rows]


@router.post("/claims/{claim_id}/activities")
def add_claim_activity(claim_id: int, payload: ClaimActivityRequest, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, CLAIMS_ROLES)
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    activity = ClaimActivity(claim_id=claim.id, created_by_id=user.id, **payload.model_dump())
    db.add(activity)
    if payload.status:
        claim.status = payload.status
    _audit(db, user, "claim.activity", {"claim_id": claim.id, "reference": claim.reference, "activity_type": payload.activity_type, "status": payload.status})
    db.commit()
    db.refresh(activity)
    return {"id": activity.id, "claim_id": claim.id, "activity_type": activity.activity_type, "status": claim.status, "created_at": _iso(activity.created_at)}


@router.post("/claims/{claim_id}/settlements")
def add_claim_settlement(claim_id: int, payload: ClaimSettlementRequest, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, CLAIMS_ROLES)
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    profile = db.query(ClaimProfile).filter(ClaimProfile.claim_id == claim.id).first()
    approved = float(profile.approved_amount if profile else 0)
    already_paid = db.query(func.sum(ClaimSettlement.amount)).filter(ClaimSettlement.claim_id == claim.id, ClaimSettlement.status == "Paid").scalar() or 0
    if approved > 0 and float(already_paid) + payload.amount > approved + 0.01:
        raise HTTPException(status_code=409, detail="Settlement would exceed the approved claim amount")
    paid_at = payload.paid_at
    if payload.status == "Paid" and paid_at is None:
        paid_at = datetime.utcnow()
    row = ClaimSettlement(
        claim_id=claim.id,
        reference=f"CLM-PAY-{datetime.utcnow():%Y%m%d}-{secrets.token_hex(3).upper()}",
        amount=payload.amount,
        payment_type=payload.payment_type,
        status=payload.status,
        payment_reference=payload.payment_reference,
        paid_at=paid_at,
        created_by_id=user.id,
    )
    db.add(row)
    if payload.status == "Paid":
        claim.status = "Paid"
    _audit(db, user, "claim.settlement", {"claim_id": claim.id, "reference": claim.reference, "amount": payload.amount, "status": payload.status})
    db.commit()
    db.refresh(row)
    return {"id": row.id, "reference": row.reference, "amount": row.amount, "status": row.status, "claim_status": claim.status}


@router.get("/claims/{claim_id}/history")
def claim_history(claim_id: int, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    activities = db.query(ClaimActivity).filter(ClaimActivity.claim_id == claim.id).order_by(ClaimActivity.created_at.desc()).all()
    settlements = db.query(ClaimSettlement).filter(ClaimSettlement.claim_id == claim.id).order_by(ClaimSettlement.created_at.desc()).all()
    return {
        "claim": {"id": claim.id, "reference": claim.reference, "status": claim.status},
        "activities": [{"id": x.id, "activity_type": x.activity_type, "status": x.status, "amount": x.amount, "notes": x.notes, "created_at": _iso(x.created_at)} for x in activities],
        "settlements": [{"id": x.id, "reference": x.reference, "amount": x.amount, "payment_type": x.payment_type, "status": x.status, "payment_reference": x.payment_reference, "paid_at": _iso(x.paid_at), "created_at": _iso(x.created_at)} for x in settlements],
    }


def _kyc_dict(row: CustomerKYC | None) -> dict | None:
    if not row:
        return None
    return {
        "id": row.id,
        "customer_id": row.customer_id,
        "verification_status": row.verification_status,
        "identity_type": row.identity_type,
        "identity_number": row.identity_number,
        "proof_of_address_status": row.proof_of_address_status,
        "pep_status": row.pep_status,
        "sanctions_status": row.sanctions_status,
        "risk_rating": row.risk_rating,
        "notes": row.notes,
        "reviewed_by_id": row.reviewed_by_id,
        "reviewed_at": _iso(row.reviewed_at),
        "updated_at": _iso(row.updated_at),
    }


@router.put("/customers/{customer_id}/kyc")
def update_kyc(customer_id: int, payload: KYCUpdateRequest, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, MANAGER_ROLES | {"Underwriter"})
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    row = db.query(CustomerKYC).filter(CustomerKYC.customer_id == customer.id).first()
    values = payload.model_dump()
    if not row:
        row = CustomerKYC(customer_id=customer.id, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    row.reviewed_by_id = user.id
    row.reviewed_at = datetime.utcnow()
    _audit(db, user, "customer.kyc", {"customer_id": customer.id, "verification_status": row.verification_status, "risk_rating": row.risk_rating})
    db.commit()
    db.refresh(row)
    return _kyc_dict(row)


@router.get("/customers/{customer_id}/360")
def customer_360(customer_id: int, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    policy_rows = (
        db.query(Policy, PolicyProfile, Customer, InsuranceProduct, StaffUser)
        .join(PolicyProfile, PolicyProfile.policy_id == Policy.id)
        .join(Customer, Customer.id == PolicyProfile.customer_id)
        .outerjoin(InsuranceProduct, InsuranceProduct.id == PolicyProfile.product_id)
        .outerjoin(StaffUser, StaffUser.id == PolicyProfile.agent_id)
        .filter(PolicyProfile.customer_id == customer.id)
        .all()
    )
    policies = [_policy_dict(*row) for row in policy_rows]
    policy_ids = [x[0].id for x in policy_rows]
    policy_numbers = [x[0].policy_number for x in policy_rows]
    quote_rows = (
        db.query(UnderwritingQuote, Customer, InsuranceProduct, StaffUser)
        .outerjoin(Customer, Customer.id == UnderwritingQuote.customer_id)
        .join(InsuranceProduct, InsuranceProduct.id == UnderwritingQuote.product_id)
        .outerjoin(StaffUser, StaffUser.id == UnderwritingQuote.underwriter_id)
        .filter(UnderwritingQuote.customer_id == customer.id)
        .order_by(UnderwritingQuote.created_at.desc())
        .all()
    )
    claims = db.query(Claim).filter(Claim.policy_number.in_(policy_numbers)).order_by(Claim.created_at.desc()).all() if policy_numbers else []
    payments = db.query(PremiumPayment).filter(or_(PremiumPayment.customer_id == customer.id, PremiumPayment.policy_id.in_(policy_ids) if policy_ids else False)).order_by(PremiumPayment.created_at.desc()).all()
    tasks = db.query(WorkTask).filter(or_(
        (WorkTask.entity_type == "customer") & (WorkTask.entity_id == customer.id),
        (WorkTask.entity_type == "policy") & (WorkTask.entity_id.in_(policy_ids) if policy_ids else False),
    )).order_by(WorkTask.created_at.desc()).all()
    notes = db.query(CaseNote).filter(CaseNote.entity_type == "customer", CaseNote.entity_id == customer.id).order_by(CaseNote.created_at.desc()).all()
    docs = db.query(ManagedDocument).filter(ManagedDocument.entity_type == "customer", ManagedDocument.entity_id == customer.id).order_by(ManagedDocument.created_at.desc()).all()
    kyc = db.query(CustomerKYC).filter(CustomerKYC.customer_id == customer.id).first()
    claim_paid = 0.0
    if claims:
        claim_ids = [x.id for x in claims]
        claim_paid = float(db.query(func.sum(ClaimSettlement.amount)).filter(ClaimSettlement.claim_id.in_(claim_ids), ClaimSettlement.status == "Paid").scalar() or 0)
    outstanding = sum(max(0, float(x.amount or 0) - float(x.paid_amount or 0)) for x in payments)
    return {
        "customer": _customer_dict(customer),
        "kyc": _kyc_dict(kyc),
        "policies": policies,
        "quotes": [_quote_dict(*row) for row in quote_rows],
        "claims": [{"id": x.id, "reference": x.reference, "policy_number": x.policy_number, "loss_date": _iso(x.loss_date), "status": x.status, "estimated_damage": x.estimated_damage, "created_at": _iso(x.created_at)} for x in claims],
        "payments": [_payment_dict(x, db.query(Policy).filter(Policy.id == x.policy_id).first(), customer) for x in payments],
        "tasks": [{"id": x.id, "reference": x.reference, "title": x.title, "status": x.status, "priority": x.priority, "due_at": _iso(x.due_at)} for x in tasks],
        "notes": [{"id": x.id, "body": x.body, "author_id": x.author_id, "created_at": _iso(x.created_at)} for x in notes],
        "documents": [{"id": x.id, "filename": x.filename, "mime_type": x.mime_type, "size_bytes": x.size_bytes, "created_at": _iso(x.created_at)} for x in docs],
        "summary": {"policy_count": len(policies), "claim_count": len(claims), "quote_count": len(quote_rows), "premium_outstanding": round(outstanding, 2), "claims_paid": round(claim_paid, 2)},
    }


def _intermediary_dict(row: Intermediary) -> dict:
    return {"id": row.id, "code": row.code, "name": row.name, "intermediary_type": row.intermediary_type, "email": row.email, "mobile": row.mobile, "commission_rate": row.commission_rate, "active": row.active, "created_at": _iso(row.created_at)}


@router.get("/intermediaries")
def list_intermediaries(active: bool | None = None, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(Intermediary)
    if active is not None:
        query = query.filter(Intermediary.active == active)
    return [_intermediary_dict(x) for x in query.order_by(Intermediary.name).all()]


@router.post("/intermediaries")
def create_intermediary(payload: IntermediaryCreateRequest, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, MANAGER_ROLES)
    code = payload.code.strip().upper()
    if db.query(Intermediary).filter(Intermediary.code == code).first():
        raise HTTPException(status_code=409, detail="Intermediary code already exists")
    row = Intermediary(**{**payload.model_dump(), "code": code})
    db.add(row)
    db.flush()
    _audit(db, user, "intermediary.created", {"intermediary_id": row.id, "code": row.code})
    db.commit()
    db.refresh(row)
    return _intermediary_dict(row)


@router.patch("/intermediaries/{intermediary_id}")
def update_intermediary(intermediary_id: int, payload: IntermediaryUpdateRequest, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, MANAGER_ROLES)
    row = db.query(Intermediary).filter(Intermediary.id == intermediary_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Intermediary not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    _audit(db, user, "intermediary.updated", {"intermediary_id": row.id})
    db.commit()
    db.refresh(row)
    return _intermediary_dict(row)


@router.put("/policies/{policy_id}/intermediary")
def assign_intermediary(policy_id: int, payload: PolicyIntermediaryRequest, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, UNDERWRITING_ROLES)
    policy, _ = _policy_with_profile(db, policy_id)
    intermediary = db.query(Intermediary).filter(Intermediary.id == payload.intermediary_id, Intermediary.active.is_(True)).first()
    if not intermediary:
        raise HTTPException(status_code=404, detail="Active intermediary not found")
    rate = intermediary.commission_rate if payload.commission_rate is None else payload.commission_rate
    row = db.query(PolicyIntermediary).filter(PolicyIntermediary.policy_id == policy.id).first()
    if not row:
        row = PolicyIntermediary(policy_id=policy.id, intermediary_id=intermediary.id, commission_rate=rate, earned_commission=policy.premium * rate / 100)
        db.add(row)
    else:
        row.intermediary_id = intermediary.id
        row.commission_rate = rate
        row.earned_commission = policy.premium * rate / 100
    _audit(db, user, "policy.intermediary", {"policy_id": policy.id, "intermediary_id": intermediary.id, "commission_rate": rate})
    db.commit()
    return {"policy_id": policy.id, "intermediary": intermediary.name, "commission_rate": rate, "earned_commission": round(row.earned_commission, 2)}


def _pdf_response(title: str, filename: str, lines: list[tuple[str, str]]) -> StreamingResponse:
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    pdf.setTitle(title)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(22 * mm, height - 25 * mm, "ZENITH HORIZON INSURANCE")
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(22 * mm, height - 36 * mm, title)
    y = height - 50 * mm
    pdf.setFont("Helvetica", 9.5)
    for label, value in lines:
        if y < 25 * mm:
            pdf.showPage()
            y = height - 25 * mm
            pdf.setFont("Helvetica", 9.5)
        pdf.setFont("Helvetica-Bold", 9.5)
        pdf.drawString(22 * mm, y, f"{label}:")
        pdf.setFont("Helvetica", 9.5)
        pdf.drawString(65 * mm, y, str(value or "—")[:100])
        y -= 7 * mm
    pdf.setFont("Helvetica-Oblique", 7.5)
    pdf.drawString(22 * mm, 14 * mm, "Generated by Zenith Insurance Management System. Policy wording, underwriting approval and terms govern cover.")
    pdf.save()
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/quotes/{quote_id}/pdf")
def quote_pdf(quote_id: int, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    row = (
        db.query(UnderwritingQuote, Customer, InsuranceProduct, StaffUser)
        .outerjoin(Customer, Customer.id == UnderwritingQuote.customer_id)
        .join(InsuranceProduct, InsuranceProduct.id == UnderwritingQuote.product_id)
        .outerjoin(StaffUser, StaffUser.id == UnderwritingQuote.underwriter_id)
        .filter(UnderwritingQuote.id == quote_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Quotation not found")
    q, customer, product, underwriter = row
    return _pdf_response(
        f"Quotation {q.reference}",
        f"{q.reference}.pdf",
        [
            ("Customer", customer.full_name if customer else "Unlinked prospect"),
            ("Product", product.name),
            ("Status", q.status),
            ("Sum insured", f"{product.currency} {q.sum_insured:,.2f}"),
            ("Excess", f"{product.currency} {q.excess_amount:,.2f}"),
            ("Base premium", f"{product.currency} {q.base_premium:,.2f}"),
            ("Loadings", f"{product.currency} {q.loading_amount:,.2f}"),
            ("Discounts", f"{product.currency} {q.discount_amount:,.2f}"),
            ("Taxes / levies", f"{product.currency} {q.tax_amount:,.2f}"),
            ("Total premium", f"{product.currency} {q.total_premium:,.2f}"),
            ("Valid until", _iso(q.valid_until)),
            ("Underwriter", underwriter.full_name if underwriter else "Not assigned"),
            ("Referral", q.referral_reason or "None"),
        ],
    )


@router.get("/policies/{policy_id}/schedule.pdf")
def policy_schedule_pdf(policy_id: int, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    policy, profile = _policy_with_profile(db, policy_id)
    customer = db.query(Customer).filter(Customer.id == profile.customer_id).first()
    product = db.query(InsuranceProduct).filter(InsuranceProduct.id == profile.product_id).first() if profile.product_id else None
    return _pdf_response(
        f"Policy Schedule {policy.policy_number}",
        f"{policy.policy_number}-schedule.pdf",
        [
            ("Policy number", policy.policy_number),
            ("Policyholder", customer.full_name if customer else policy.holder_name),
            ("Product", product.name if product else policy.product),
            ("Status", policy.status),
            ("Effective date", _iso(profile.effective_date)),
            ("Expiry date", _iso(profile.expiry_date)),
            ("Sum insured", f"{policy.currency} {float(profile.sum_insured or 0):,.2f}"),
            ("Premium", f"{policy.currency} {policy.premium:,.2f}"),
            ("Payment frequency", profile.payment_frequency),
            ("Payment status", profile.payment_status),
            ("Risk address", profile.risk_address or "—"),
        ],
    )


@router.get("/reports/executive")
def executive_report(user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, MANAGER_ROLES | {"Finance", "Claims", "Underwriter"})
    written_premium = float(db.query(func.sum(Policy.premium)).filter(Policy.status.in_(["Active", "Expired"])).scalar() or 0)
    premium_collected = float(db.query(func.sum(PremiumPayment.paid_amount)).scalar() or 0)
    outstanding = float(db.query(func.sum(PremiumPayment.amount - PremiumPayment.paid_amount)).filter(PremiumPayment.status != "Paid").scalar() or 0)
    claims_paid = float(db.query(func.sum(ClaimSettlement.amount)).filter(ClaimSettlement.status == "Paid").scalar() or 0)
    claims_reserve = float(db.query(func.sum(ClaimProfile.reserve_amount)).scalar() or 0)
    active_policies = db.query(func.count(Policy.id)).filter(Policy.status == "Active").scalar() or 0
    cancelled = db.query(func.count(PolicyTransaction.id)).filter(PolicyTransaction.transaction_type == "Cancel").scalar() or 0
    renewals = db.query(func.count(PolicyTransaction.id)).filter(PolicyTransaction.transaction_type == "Renew").scalar() or 0
    quotes = db.query(func.count(UnderwritingQuote.id)).scalar() or 0
    converted = db.query(func.count(UnderwritingQuote.id)).filter(UnderwritingQuote.status == "Converted").scalar() or 0
    open_claims = db.query(func.count(Claim.id)).filter(Claim.status.notin_(["Closed", "Rejected", "Paid"])).scalar() or 0
    return {
        "written_premium": written_premium,
        "premium_collected": premium_collected,
        "premium_outstanding": outstanding,
        "claims_paid": claims_paid,
        "claims_reserve": claims_reserve,
        "loss_ratio_pct": round((claims_paid / premium_collected * 100) if premium_collected else 0, 2),
        "active_policies": active_policies,
        "renewals": renewals,
        "cancellations": cancelled,
        "open_claims": open_claims,
        "quotes": quotes,
        "quote_conversion_pct": round((converted / quotes * 100) if quotes else 0, 2),
        "generated_at": datetime.utcnow().isoformat(),
        "basis_note": "Written premium is based on policy premium values currently stored in the management database; financial reporting definitions should be aligned to Zenith accounting policy before statutory use.",
    }
