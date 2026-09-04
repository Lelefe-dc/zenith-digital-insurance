from __future__ import annotations

import csv
import io
import json
import mimetypes
import re
import secrets
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import AuditEvent, Claim, Lead, Policy
from .management_models import (
    Branch,
    CaseNote,
    ClaimProfile,
    Customer,
    InsuranceProduct,
    LeadProfile,
    ManagedDocument,
    ManagementSession,
    PolicyProfile,
    PremiumPayment,
    StaffUser,
    SystemSetting,
    WorkTask,
)
from .management_schemas import (
    BranchCreate,
    BranchUpdate,
    ClaimUpdate,
    CustomerCreate,
    CustomerUpdate,
    LeadUpdate,
    LoginRequest,
    NoteCreate,
    PaymentCreate,
    PaymentUpdate,
    PolicyCreate,
    PolicyUpdate,
    ProductCreate,
    ProductUpdate,
    SettingUpdate,
    StaffCreate,
    StaffUpdate,
    TaskCreate,
    TaskUpdate,
)
from .security import hash_password, hash_token, verify_password

settings = get_settings()
router = APIRouter(prefix="/api/v1/management", tags=["Management"])

ADMIN_ROLES = {"Administrator"}
MANAGER_ROLES = {"Administrator", "Manager"}
FINANCE_ROLES = {"Administrator", "Manager", "Finance"}
CLAIMS_ROLES = {"Administrator", "Manager", "Claims"}
UNDERWRITING_ROLES = {"Administrator", "Manager", "Underwriter"}


def _iso(value):
    return value.isoformat() if value else None


def _user_dict(user: StaffUser) -> dict:
    return {
        "id": user.id,
        "employee_number": user.employee_number,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "department": user.department,
        "branch_id": user.branch_id,
        "active": user.active,
        "last_login_at": _iso(user.last_login_at),
        "created_at": _iso(user.created_at),
    }


def _audit(db: Session, user: StaffUser | None, event: str, payload: dict) -> None:
    body = dict(payload)
    if user:
        body["staff_user_id"] = user.id
        body["staff_user"] = user.email
    db.add(AuditEvent(session_id=None, event_type=f"management.{event}", payload_json=json.dumps(body, default=str)))


def _require(user: StaffUser, allowed: set[str]) -> None:
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Your role does not have permission for this action")


def _token_from_headers(authorization: str | None, x_management_token: str | None) -> str | None:
    if x_management_token:
        return x_management_token.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def current_user(
    authorization: str | None = Header(None),
    x_management_token: str | None = Header(None),
    db: Session = Depends(get_db),
) -> StaffUser:
    token = _token_from_headers(authorization, x_management_token)
    if not token:
        raise HTTPException(status_code=401, detail="Management authentication required")
    session = db.query(ManagementSession).filter(ManagementSession.token_hash == hash_token(token)).first()
    if not session or session.expires_at <= datetime.utcnow():
        if session:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=401, detail="Management session has expired")
    user = db.query(StaffUser).filter(StaffUser.id == session.user_id, StaffUser.active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Management account is inactive")
    return user


def _new_ref(prefix: str) -> str:
    return f"{prefix}-{datetime.utcnow():%Y%m%d}-{secrets.token_hex(3).upper()}"


def _new_customer_number() -> str:
    return f"CUS-{datetime.utcnow():%Y}-{secrets.token_hex(3).upper()}"


def _new_employee_number() -> str:
    return f"EMP-{secrets.token_hex(3).upper()}"


def _customer_dict(row: Customer) -> dict:
    return {
        "id": row.id,
        "customer_number": row.customer_number,
        "full_name": row.full_name,
        "national_id": row.national_id,
        "date_of_birth": _iso(row.date_of_birth),
        "mobile": row.mobile,
        "email": row.email,
        "address": row.address,
        "district": row.district,
        "occupation": row.occupation,
        "status": row.status,
        "source": row.source,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _product_dict(row: InsuranceProduct) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "category": row.category,
        "description": row.description,
        "base_premium": row.base_premium,
        "currency": row.currency,
        "active": row.active,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _branch_dict(row: Branch) -> dict:
    return {"id": row.id, "code": row.code, "name": row.name, "location": row.location, "active": row.active}


def _policy_dict(policy: Policy, profile: PolicyProfile | None, customer: Customer | None, product: InsuranceProduct | None, staff: StaffUser | None = None) -> dict:
    return {
        "id": policy.id,
        "policy_number": policy.policy_number,
        "holder_name": policy.holder_name,
        "status": policy.status,
        "product": product.name if product else policy.product,
        "product_id": profile.product_id if profile else None,
        "customer_id": profile.customer_id if profile else None,
        "customer_number": customer.customer_number if customer else None,
        "premium": policy.premium,
        "currency": policy.currency,
        "effective_date": _iso(profile.effective_date) if profile else None,
        "expiry_date": _iso(profile.expiry_date) if profile else None,
        "sum_insured": profile.sum_insured if profile else None,
        "payment_frequency": profile.payment_frequency if profile else None,
        "payment_status": profile.payment_status if profile else None,
        "branch_id": profile.branch_id if profile else None,
        "agent_id": profile.agent_id if profile else None,
        "agent_name": staff.full_name if staff else None,
        "risk_address": profile.risk_address if profile else None,
        "notes": profile.notes if profile else None,
    }


def _payment_dict(row: PremiumPayment, policy: Policy | None = None, customer: Customer | None = None) -> dict:
    return {
        "id": row.id,
        "reference": row.reference,
        "policy_id": row.policy_id,
        "policy_number": policy.policy_number if policy else None,
        "customer_id": row.customer_id,
        "customer_name": customer.full_name if customer else None,
        "due_date": _iso(row.due_date),
        "amount": row.amount,
        "paid_amount": row.paid_amount,
        "currency": row.currency,
        "method": row.method,
        "status": row.status,
        "transaction_reference": row.transaction_reference,
        "paid_at": _iso(row.paid_at),
        "created_at": _iso(row.created_at),
    }


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(StaffUser).filter(func.lower(StaffUser.email) == payload.email.lower()).first()
    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    db.query(ManagementSession).filter(ManagementSession.expires_at <= datetime.utcnow()).delete(synchronize_session=False)
    raw_token = secrets.token_urlsafe(40)
    expiry = datetime.utcnow() + timedelta(hours=max(1, settings.management_session_hours))
    db.add(ManagementSession(id=str(uuid.uuid4()), user_id=user.id, token_hash=hash_token(raw_token), expires_at=expiry))
    user.last_login_at = datetime.utcnow()
    _audit(db, user, "login", {})
    db.commit()
    return {"token": raw_token, "expires_at": expiry.isoformat(), "user": _user_dict(user)}


@router.post("/auth/logout")
def logout(
    authorization: str | None = Header(None),
    x_management_token: str | None = Header(None),
    user: StaffUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    token = _token_from_headers(authorization, x_management_token)
    if token:
        db.query(ManagementSession).filter(ManagementSession.token_hash == hash_token(token)).delete(synchronize_session=False)
    _audit(db, user, "logout", {})
    db.commit()
    return {"status": "ok"}


@router.get("/auth/me")
def me(user: StaffUser = Depends(current_user)):
    return _user_dict(user)


@router.get("/dashboard")
def dashboard(user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    active_policies = db.query(func.count(Policy.id)).filter(Policy.status == "Active").scalar() or 0
    open_claims = db.query(func.count(Claim.id)).filter(Claim.status.notin_(["Closed", "Rejected", "Paid"])).scalar() or 0
    open_tasks = db.query(func.count(WorkTask.id)).filter(WorkTask.status.notin_(["Completed", "Cancelled"])).scalar() or 0
    outstanding = db.query(func.sum(PremiumPayment.amount - PremiumPayment.paid_amount)).filter(PremiumPayment.status != "Paid").scalar() or 0
    collected = db.query(func.sum(PremiumPayment.paid_amount)).filter(PremiumPayment.status == "Paid").scalar() or 0
    claims_reserve = db.query(func.sum(ClaimProfile.reserve_amount)).scalar() or 0
    recent_tasks = db.query(WorkTask).filter(WorkTask.status.notin_(["Completed", "Cancelled"])).order_by(WorkTask.due_at.asc()).limit(8).all()
    recent_claims = db.query(Claim).order_by(Claim.created_at.desc()).limit(6).all()
    return {
        "metrics": {
            "customers": db.query(func.count(Customer.id)).scalar() or 0,
            "active_policies": active_policies,
            "leads": db.query(func.count(Lead.id)).scalar() or 0,
            "open_claims": open_claims,
            "premium_collected": float(collected),
            "premium_outstanding": float(outstanding),
            "claims_reserve": float(claims_reserve),
            "open_tasks": open_tasks,
        },
        "tasks": [{"id": x.id, "reference": x.reference, "title": x.title, "priority": x.priority, "status": x.status, "due_at": _iso(x.due_at)} for x in recent_tasks],
        "claims": [{"id": x.id, "reference": x.reference, "policy_number": x.policy_number, "status": x.status, "loss_date": _iso(x.loss_date), "created_at": _iso(x.created_at)} for x in recent_claims],
        "user": _user_dict(user),
    }


@router.get("/customers")
def list_customers(
    q: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user: StaffUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Customer)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Customer.full_name.ilike(like), Customer.customer_number.ilike(like), Customer.mobile.ilike(like), Customer.email.ilike(like)))
    if status:
        query = query.filter(Customer.status == status)
    rows = query.order_by(Customer.created_at.desc()).limit(limit).all()
    return [_customer_dict(x) for x in rows]


@router.post("/customers")
def create_customer(payload: CustomerCreate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    if payload.national_id and db.query(Customer).filter(Customer.national_id == payload.national_id).first():
        raise HTTPException(status_code=409, detail="A customer with that national ID already exists")
    customer = Customer(customer_number=_new_customer_number(), **payload.model_dump())
    db.add(customer)
    db.flush()
    _audit(db, user, "customer.created", {"customer_id": customer.id, "customer_number": customer.customer_number})
    db.commit()
    db.refresh(customer)
    return _customer_dict(customer)


@router.get("/customers/{customer_id}")
def get_customer(customer_id: int, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    policy_rows = (
        db.query(Policy, PolicyProfile, InsuranceProduct, StaffUser)
        .join(PolicyProfile, PolicyProfile.policy_id == Policy.id)
        .outerjoin(InsuranceProduct, InsuranceProduct.id == PolicyProfile.product_id)
        .outerjoin(StaffUser, StaffUser.id == PolicyProfile.agent_id)
        .filter(PolicyProfile.customer_id == customer.id)
        .order_by(Policy.id.desc())
        .all()
    )
    notes = db.query(CaseNote).filter(CaseNote.entity_type == "customer", CaseNote.entity_id == customer.id).order_by(CaseNote.created_at.desc()).all()
    docs = db.query(ManagedDocument).filter(ManagedDocument.entity_type == "customer", ManagedDocument.entity_id == customer.id).order_by(ManagedDocument.created_at.desc()).all()
    return {
        **_customer_dict(customer),
        "policies": [_policy_dict(p, pf, customer, prod, staff) for p, pf, prod, staff in policy_rows],
        "notes": [{"id": n.id, "body": n.body, "author_id": n.author_id, "created_at": _iso(n.created_at)} for n in notes],
        "documents": [{"id": d.id, "filename": d.filename, "mime_type": d.mime_type, "size_bytes": d.size_bytes, "created_at": _iso(d.created_at)} for d in docs],
    }


@router.patch("/customers/{customer_id}")
def update_customer(customer_id: int, payload: CustomerUpdate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    _audit(db, user, "customer.updated", {"customer_id": row.id})
    db.commit(); db.refresh(row)
    return _customer_dict(row)


@router.get("/products")
def list_products(active: bool | None = None, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(InsuranceProduct)
    if active is not None:
        query = query.filter(InsuranceProduct.active == active)
    return [_product_dict(x) for x in query.order_by(InsuranceProduct.name).all()]


@router.post("/products")
def create_product(payload: ProductCreate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, UNDERWRITING_ROLES)
    code = payload.code.strip().upper()
    if db.query(InsuranceProduct).filter(InsuranceProduct.code == code).first():
        raise HTTPException(status_code=409, detail="Product code already exists")
    row = InsuranceProduct(**{**payload.model_dump(), "code": code})
    db.add(row); db.flush(); _audit(db, user, "product.created", {"product_id": row.id, "code": row.code}); db.commit(); db.refresh(row)
    return _product_dict(row)


@router.patch("/products/{product_id}")
def update_product(product_id: int, payload: ProductUpdate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, UNDERWRITING_ROLES)
    row = db.query(InsuranceProduct).filter(InsuranceProduct.id == product_id).first()
    if not row: raise HTTPException(status_code=404, detail="Product not found")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(row, key, value)
    _audit(db, user, "product.updated", {"product_id": row.id}); db.commit(); db.refresh(row)
    return _product_dict(row)


@router.get("/branches")
def list_branches(user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    return [_branch_dict(x) for x in db.query(Branch).order_by(Branch.name).all()]


@router.post("/branches")
def create_branch(payload: BranchCreate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, ADMIN_ROLES)
    code = payload.code.strip().upper()
    if db.query(Branch).filter(Branch.code == code).first(): raise HTTPException(status_code=409, detail="Branch code already exists")
    row = Branch(**{**payload.model_dump(), "code": code}); db.add(row); db.flush(); _audit(db, user, "branch.created", {"branch_id": row.id}); db.commit(); db.refresh(row)
    return _branch_dict(row)


@router.patch("/branches/{branch_id}")
def update_branch(branch_id: int, payload: BranchUpdate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, ADMIN_ROLES)
    row = db.query(Branch).filter(Branch.id == branch_id).first()
    if not row: raise HTTPException(status_code=404, detail="Branch not found")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(row, key, value)
    _audit(db, user, "branch.updated", {"branch_id": row.id}); db.commit(); db.refresh(row)
    return _branch_dict(row)


@router.get("/policies")
def list_policies(
    q: str | None = None,
    status: str | None = None,
    limit: int = Query(200, ge=1, le=500),
    user: StaffUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Policy, PolicyProfile, Customer, InsuranceProduct, StaffUser)
        .outerjoin(PolicyProfile, PolicyProfile.policy_id == Policy.id)
        .outerjoin(Customer, Customer.id == PolicyProfile.customer_id)
        .outerjoin(InsuranceProduct, InsuranceProduct.id == PolicyProfile.product_id)
        .outerjoin(StaffUser, StaffUser.id == PolicyProfile.agent_id)
    )
    if q:
        like = f"%{q.strip()}%"; query = query.filter(or_(Policy.policy_number.ilike(like), Policy.holder_name.ilike(like), Customer.customer_number.ilike(like)))
    if status: query = query.filter(Policy.status == status)
    return [_policy_dict(*row) for row in query.order_by(Policy.id.desc()).limit(limit).all()]


@router.post("/policies")
def create_policy(payload: PolicyCreate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, UNDERWRITING_ROLES)
    customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
    product = db.query(InsuranceProduct).filter(InsuranceProduct.id == payload.product_id, InsuranceProduct.active.is_(True)).first()
    if not customer: raise HTTPException(status_code=404, detail="Customer not found")
    if not product: raise HTTPException(status_code=404, detail="Active product not found")
    if not customer.date_of_birth: raise HTTPException(status_code=422, detail="Customer date of birth is required before a policy can be issued")
    number = (payload.policy_number or f"ZEN-{datetime.utcnow():%Y}-{secrets.token_hex(4).upper()}").strip().upper()
    if db.query(Policy).filter(Policy.policy_number == number).first(): raise HTTPException(status_code=409, detail="Policy number already exists")
    policy = Policy(policy_number=number, holder_name=customer.full_name, dob=customer.date_of_birth, status=payload.status, product=product.name, premium=payload.premium, currency=product.currency)
    db.add(policy); db.flush()
    profile = PolicyProfile(
        policy_id=policy.id, customer_id=customer.id, product_id=product.id, branch_id=payload.branch_id, agent_id=payload.agent_id,
        effective_date=payload.effective_date, expiry_date=payload.expiry_date, sum_insured=payload.sum_insured,
        payment_frequency=payload.payment_frequency, payment_status=payload.payment_status, risk_address=payload.risk_address, notes=payload.notes,
    )
    db.add(profile); db.flush(); _audit(db, user, "policy.created", {"policy_id": policy.id, "policy_number": policy.policy_number, "customer_id": customer.id}); db.commit()
    staff = db.query(StaffUser).filter(StaffUser.id == profile.agent_id).first() if profile.agent_id else None
    return _policy_dict(policy, profile, customer, product, staff)


@router.patch("/policies/{policy_id}")
def update_policy(policy_id: int, payload: PolicyUpdate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, UNDERWRITING_ROLES)
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy: raise HTTPException(status_code=404, detail="Policy not found")
    profile = db.query(PolicyProfile).filter(PolicyProfile.policy_id == policy.id).first()
    values = payload.model_dump(exclude_unset=True)
    for key in ("status", "premium"):
        if key in values: setattr(policy, key, values.pop(key))
    if profile:
        for key, value in values.items(): setattr(profile, key, value)
    _audit(db, user, "policy.updated", {"policy_id": policy.id, "policy_number": policy.policy_number}); db.commit()
    customer = db.query(Customer).filter(Customer.id == profile.customer_id).first() if profile else None
    product = db.query(InsuranceProduct).filter(InsuranceProduct.id == profile.product_id).first() if profile and profile.product_id else None
    staff = db.query(StaffUser).filter(StaffUser.id == profile.agent_id).first() if profile and profile.agent_id else None
    return _policy_dict(policy, profile, customer, product, staff)


@router.get("/payments")
def list_payments(status: str | None = None, limit: int = Query(250, ge=1, le=500), user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(PremiumPayment, Policy, Customer).join(Policy, Policy.id == PremiumPayment.policy_id).outerjoin(Customer, Customer.id == PremiumPayment.customer_id)
    if status: query = query.filter(PremiumPayment.status == status)
    return [_payment_dict(*row) for row in query.order_by(PremiumPayment.created_at.desc()).limit(limit).all()]


@router.post("/payments")
def create_payment(payload: PaymentCreate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, FINANCE_ROLES)
    policy = db.query(Policy).filter(Policy.id == payload.policy_id).first()
    if not policy: raise HTTPException(status_code=404, detail="Policy not found")
    profile = db.query(PolicyProfile).filter(PolicyProfile.policy_id == policy.id).first()
    values = payload.model_dump()
    if values["status"] == "Paid":
        if values["paid_amount"] == 0: values["paid_amount"] = values["amount"]
        if not values["paid_at"]: values["paid_at"] = datetime.utcnow()
    row = PremiumPayment(reference=_new_ref("PAY"), customer_id=profile.customer_id if profile else None, **values)
    db.add(row); db.flush(); _audit(db, user, "payment.created", {"payment_id": row.id, "reference": row.reference, "policy_id": policy.id}); db.commit(); db.refresh(row)
    customer = db.query(Customer).filter(Customer.id == row.customer_id).first() if row.customer_id else None
    return _payment_dict(row, policy, customer)


@router.patch("/payments/{payment_id}")
def update_payment(payment_id: int, payload: PaymentUpdate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, FINANCE_ROLES)
    row = db.query(PremiumPayment).filter(PremiumPayment.id == payment_id).first()
    if not row: raise HTTPException(status_code=404, detail="Payment not found")
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items(): setattr(row, key, value)
    if row.status == "Paid":
        if not row.paid_amount: row.paid_amount = row.amount
        if not row.paid_at: row.paid_at = datetime.utcnow()
    _audit(db, user, "payment.updated", {"payment_id": row.id, "reference": row.reference}); db.commit(); db.refresh(row)
    policy = db.query(Policy).filter(Policy.id == row.policy_id).first(); customer = db.query(Customer).filter(Customer.id == row.customer_id).first() if row.customer_id else None
    return _payment_dict(row, policy, customer)


@router.get("/leads")
def list_leads(stage: str | None = None, limit: int = Query(250, ge=1, le=500), user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(Lead, LeadProfile, StaffUser).outerjoin(LeadProfile, LeadProfile.lead_id == Lead.id).outerjoin(StaffUser, StaffUser.id == LeadProfile.assigned_to_id)
    if stage: query = query.filter(or_(LeadProfile.stage == stage, Lead.status == stage))
    rows = query.order_by(Lead.created_at.desc()).limit(limit).all()
    return [{
        "id": lead.id, "reference": lead.reference, "name": lead.name, "mobile": lead.mobile, "product": lead.product,
        "stage": profile.stage if profile else lead.status, "priority": profile.priority if profile else "Normal",
        "assigned_to_id": profile.assigned_to_id if profile else None, "assigned_to": staff.full_name if staff else None,
        "next_action_at": _iso(profile.next_action_at) if profile else None, "notes": profile.notes if profile else None,
        "source": lead.source, "consent": lead.consent, "created_at": _iso(lead.created_at),
    } for lead, profile, staff in rows]


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: int, payload: LeadUpdate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead: raise HTTPException(status_code=404, detail="Lead not found")
    profile = db.query(LeadProfile).filter(LeadProfile.lead_id == lead.id).first()
    if not profile:
        profile = LeadProfile(lead_id=lead.id, stage=lead.status); db.add(profile)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items(): setattr(profile, key, value)
    if payload.stage is not None: lead.status = payload.stage
    _audit(db, user, "lead.updated", {"lead_id": lead.id, "reference": lead.reference, "stage": lead.status}); db.commit()
    return {"status": "ok", "lead_id": lead.id, "stage": lead.status}


@router.get("/claims")
def list_claims(status: str | None = None, limit: int = Query(250, ge=1, le=500), user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(Claim, ClaimProfile, StaffUser).outerjoin(ClaimProfile, ClaimProfile.claim_id == Claim.id).outerjoin(StaffUser, StaffUser.id == ClaimProfile.assigned_to_id)
    if status: query = query.filter(Claim.status == status)
    rows = query.order_by(Claim.created_at.desc()).limit(limit).all()
    return [{
        "id": claim.id, "reference": claim.reference, "policy_number": claim.policy_number, "loss_date": _iso(claim.loss_date),
        "description": claim.description, "location": claim.location, "estimated_damage": claim.estimated_damage, "contact": claim.contact, "status": claim.status,
        "priority": profile.priority if profile else "Normal", "claim_type": profile.claim_type if profile else None,
        "reserve_amount": profile.reserve_amount if profile else 0, "approved_amount": profile.approved_amount if profile else 0,
        "excess_amount": profile.excess_amount if profile else 0, "decision": profile.decision if profile else None,
        "assigned_to_id": profile.assigned_to_id if profile else None, "assigned_to": staff.full_name if staff else None,
        "next_action_at": _iso(profile.next_action_at) if profile else None, "notes": profile.notes if profile else None, "created_at": _iso(claim.created_at),
    } for claim, profile, staff in rows]


@router.patch("/claims/{claim_id}")
def update_claim(claim_id: int, payload: ClaimUpdate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, CLAIMS_ROLES)
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim: raise HTTPException(status_code=404, detail="Claim not found")
    profile = db.query(ClaimProfile).filter(ClaimProfile.claim_id == claim.id).first()
    if not profile:
        profile = ClaimProfile(claim_id=claim.id); db.add(profile)
    values = payload.model_dump(exclude_unset=True)
    if "status" in values: claim.status = values.pop("status")
    for key, value in values.items(): setattr(profile, key, value)
    if claim.status in {"Closed", "Rejected", "Paid"} and not profile.closed_at: profile.closed_at = datetime.utcnow()
    _audit(db, user, "claim.updated", {"claim_id": claim.id, "reference": claim.reference, "status": claim.status}); db.commit()
    return {"status": "ok", "claim_id": claim.id, "claim_status": claim.status}


@router.get("/tasks")
def list_tasks(status: str | None = None, assigned_to_id: int | None = None, limit: int = Query(250, ge=1, le=500), user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(WorkTask, StaffUser).outerjoin(StaffUser, StaffUser.id == WorkTask.assigned_to_id)
    if status: query = query.filter(WorkTask.status == status)
    if assigned_to_id: query = query.filter(WorkTask.assigned_to_id == assigned_to_id)
    rows = query.order_by(WorkTask.created_at.desc()).limit(limit).all()
    return [{"id": t.id, "reference": t.reference, "title": t.title, "description": t.description, "entity_type": t.entity_type, "entity_id": t.entity_id, "assigned_to_id": t.assigned_to_id, "assigned_to": staff.full_name if staff else None, "priority": t.priority, "status": t.status, "due_at": _iso(t.due_at), "completed_at": _iso(t.completed_at), "created_at": _iso(t.created_at)} for t, staff in rows]


@router.post("/tasks")
def create_task(payload: TaskCreate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    row = WorkTask(reference=_new_ref("TSK"), created_by_id=user.id, **payload.model_dump()); db.add(row); db.flush(); _audit(db, user, "task.created", {"task_id": row.id, "reference": row.reference}); db.commit(); db.refresh(row)
    return {"id": row.id, "reference": row.reference, "title": row.title, "status": row.status}


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    row = db.query(WorkTask).filter(WorkTask.id == task_id).first()
    if not row: raise HTTPException(status_code=404, detail="Task not found")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(row, key, value)
    if row.status == "Completed" and not row.completed_at: row.completed_at = datetime.utcnow()
    _audit(db, user, "task.updated", {"task_id": row.id, "status": row.status}); db.commit(); db.refresh(row)
    return {"id": row.id, "reference": row.reference, "title": row.title, "status": row.status}


@router.get("/staff")
def list_staff(user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    return [_user_dict(x) for x in db.query(StaffUser).order_by(StaffUser.full_name).all()]


@router.post("/staff")
def create_staff(payload: StaffCreate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, ADMIN_ROLES)
    email = payload.email.lower().strip()
    if db.query(StaffUser).filter(func.lower(StaffUser.email) == email).first(): raise HTTPException(status_code=409, detail="Staff email already exists")
    values = payload.model_dump(exclude={"password"})
    row = StaffUser(employee_number=_new_employee_number(), email=email, password_hash=hash_password(payload.password), **values)
    db.add(row); db.flush(); _audit(db, user, "staff.created", {"staff_id": row.id, "email": row.email, "role": row.role}); db.commit(); db.refresh(row)
    return _user_dict(row)


@router.patch("/staff/{staff_id}")
def update_staff(staff_id: int, payload: StaffUpdate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, ADMIN_ROLES)
    row = db.query(StaffUser).filter(StaffUser.id == staff_id).first()
    if not row: raise HTTPException(status_code=404, detail="Staff user not found")
    values = payload.model_dump(exclude_unset=True)
    password = values.pop("password", None)
    for key, value in values.items(): setattr(row, key, value)
    if password: row.password_hash = hash_password(password)
    _audit(db, user, "staff.updated", {"staff_id": row.id, "role": row.role, "active": row.active}); db.commit(); db.refresh(row)
    return _user_dict(row)


@router.get("/notes")
def list_notes(entity_type: str, entity_id: int, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(CaseNote, StaffUser).outerjoin(StaffUser, StaffUser.id == CaseNote.author_id).filter(CaseNote.entity_type == entity_type, CaseNote.entity_id == entity_id).order_by(CaseNote.created_at.desc()).all()
    return [{"id": note.id, "body": note.body, "author_id": note.author_id, "author": staff.full_name if staff else None, "created_at": _iso(note.created_at)} for note, staff in rows]


@router.post("/notes")
def create_note(payload: NoteCreate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    row = CaseNote(author_id=user.id, **payload.model_dump()); db.add(row); db.flush(); _audit(db, user, "note.created", {"note_id": row.id, "entity_type": row.entity_type, "entity_id": row.entity_id}); db.commit(); db.refresh(row)
    return {"id": row.id, "created_at": _iso(row.created_at)}


ALLOWED_DOCUMENT_MIME = {"image/jpeg", "image/png", "image/webp", "application/pdf", "text/plain", "text/csv", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


@router.get("/documents")
def list_documents(entity_type: str, entity_id: int, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(ManagedDocument).filter(ManagedDocument.entity_type == entity_type, ManagedDocument.entity_id == entity_id).order_by(ManagedDocument.created_at.desc()).all()
    return [{"id": x.id, "filename": x.filename, "mime_type": x.mime_type, "size_bytes": x.size_bytes, "created_at": _iso(x.created_at)} for x in rows]


@router.post("/documents")
async def upload_document(entity_type: str, entity_id: int, file: UploadFile = File(...), user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    if mime not in ALLOWED_DOCUMENT_MIME: raise HTTPException(status_code=415, detail="Unsupported document type")
    data = await file.read((settings.max_upload_mb * 1024 * 1024) + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024: raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB limit")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename or "document")
    managed_dir = Path(settings.upload_dir) / "management"; managed_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{entity_type}_{entity_id}_{secrets.token_hex(6)}_{safe_name}"; path = managed_dir / stored_name; path.write_bytes(data)
    row = ManagedDocument(entity_type=entity_type, entity_id=entity_id, filename=safe_name, stored_path=str(path), mime_type=mime, size_bytes=len(data), uploaded_by_id=user.id)
    db.add(row); db.flush(); _audit(db, user, "document.uploaded", {"document_id": row.id, "entity_type": entity_type, "entity_id": entity_id, "filename": safe_name}); db.commit(); db.refresh(row)
    return {"id": row.id, "filename": row.filename, "size_bytes": row.size_bytes}


@router.get("/settings")
def list_settings(user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, ADMIN_ROLES)
    return [{"key": x.key, "value": x.value, "category": x.category, "updated_at": _iso(x.updated_at)} for x in db.query(SystemSetting).order_by(SystemSetting.category, SystemSetting.key).all()]


@router.put("/settings/{key}")
def update_setting(key: str, payload: SettingUpdate, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, ADMIN_ROLES)
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not row:
        row = SystemSetting(key=key, value=payload.value, category=payload.category, updated_by_id=user.id); db.add(row)
    else:
        row.value = payload.value; row.category = payload.category; row.updated_by_id = user.id
    _audit(db, user, "setting.updated", {"key": key}); db.commit()
    return {"key": row.key, "value": row.value, "category": row.category}


@router.get("/reports/summary")
def reports_summary(user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, MANAGER_ROLES | {"Finance", "Claims", "Underwriter"})
    products = db.query(Policy.product, func.count(Policy.id), func.sum(Policy.premium)).group_by(Policy.product).order_by(func.count(Policy.id).desc()).all()
    claim_status = db.query(Claim.status, func.count(Claim.id)).group_by(Claim.status).all()
    lead_status = db.query(Lead.status, func.count(Lead.id)).group_by(Lead.status).all()
    payment_status = db.query(PremiumPayment.status, func.count(PremiumPayment.id), func.sum(PremiumPayment.amount), func.sum(PremiumPayment.paid_amount)).group_by(PremiumPayment.status).all()
    task_status = db.query(WorkTask.status, func.count(WorkTask.id)).group_by(WorkTask.status).all()
    return {
        "policies_by_product": [{"product": name, "count": count, "premium": float(total or 0)} for name, count, total in products],
        "claims_by_status": [{"status": status, "count": count} for status, count in claim_status],
        "leads_by_status": [{"status": status, "count": count} for status, count in lead_status],
        "payments_by_status": [{"status": status, "count": count, "amount": float(amount or 0), "paid": float(paid or 0)} for status, count, amount, paid in payment_status],
        "tasks_by_status": [{"status": status, "count": count} for status, count in task_status],
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/exports/{dataset}")
def export_dataset(dataset: str, user: StaffUser = Depends(current_user), db: Session = Depends(get_db)):
    _require(user, MANAGER_ROLES | {"Finance", "Claims", "Underwriter"})
    output = io.StringIO(); writer = csv.writer(output)
    if dataset == "customers":
        writer.writerow(["Customer Number", "Name", "National ID", "DOB", "Mobile", "Email", "District", "Status"])
        for x in db.query(Customer).order_by(Customer.id).all(): writer.writerow([x.customer_number, x.full_name, x.national_id, x.date_of_birth, x.mobile, x.email, x.district, x.status])
    elif dataset == "policies":
        writer.writerow(["Policy Number", "Holder", "Product", "Status", "Premium", "Currency"])
        for x in db.query(Policy).order_by(Policy.id).all(): writer.writerow([x.policy_number, x.holder_name, x.product, x.status, x.premium, x.currency])
    elif dataset == "claims":
        writer.writerow(["Reference", "Policy Number", "Loss Date", "Location", "Estimated Damage", "Status", "Created"])
        for x in db.query(Claim).order_by(Claim.id).all(): writer.writerow([x.reference, x.policy_number, x.loss_date, x.location, x.estimated_damage, x.status, x.created_at])
    elif dataset == "leads":
        writer.writerow(["Reference", "Name", "Mobile", "Product", "Status", "Source", "Created"])
        for x in db.query(Lead).order_by(Lead.id).all(): writer.writerow([x.reference, x.name, x.mobile, x.product, x.status, x.source, x.created_at])
    elif dataset == "payments":
        writer.writerow(["Reference", "Policy ID", "Due Date", "Amount", "Paid", "Currency", "Method", "Status", "Transaction"])
        for x in db.query(PremiumPayment).order_by(PremiumPayment.id).all(): writer.writerow([x.reference, x.policy_id, x.due_date, x.amount, x.paid_amount, x.currency, x.method, x.status, x.transaction_reference])
    elif dataset == "tasks":
        writer.writerow(["Reference", "Title", "Entity", "Entity ID", "Priority", "Status", "Due"])
        for x in db.query(WorkTask).order_by(WorkTask.id).all(): writer.writerow([x.reference, x.title, x.entity_type, x.entity_id, x.priority, x.status, x.due_at])
    else:
        raise HTTPException(status_code=404, detail="Unknown export dataset")
    filename = f"zenith-{dataset}-{date.today().isoformat()}.csv"
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
