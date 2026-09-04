from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class CustomerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=180)
    national_id: str | None = None
    date_of_birth: date | None = None
    mobile: str = Field(min_length=5, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    district: str | None = None
    occupation: str | None = None
    status: str = "Active"


class CustomerUpdate(BaseModel):
    full_name: str | None = None
    national_id: str | None = None
    date_of_birth: date | None = None
    mobile: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    district: str | None = None
    occupation: str | None = None
    status: str | None = None


class ProductCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=100)
    description: str | None = None
    base_premium: float = Field(default=0, ge=0)
    currency: str = "LSL"
    active: bool = True


class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    base_premium: float | None = Field(default=None, ge=0)
    currency: str | None = None
    active: bool | None = None


class PolicyCreate(BaseModel):
    customer_id: int
    product_id: int
    policy_number: str | None = None
    status: str = "Active"
    premium: float = Field(gt=0)
    effective_date: date
    expiry_date: date | None = None
    sum_insured: float | None = Field(default=None, ge=0)
    payment_frequency: str = "Monthly"
    payment_status: str = "Current"
    branch_id: int | None = None
    agent_id: int | None = None
    risk_address: str | None = None
    notes: str | None = None


class PolicyUpdate(BaseModel):
    status: str | None = None
    premium: float | None = Field(default=None, gt=0)
    expiry_date: date | None = None
    sum_insured: float | None = Field(default=None, ge=0)
    payment_frequency: str | None = None
    payment_status: str | None = None
    branch_id: int | None = None
    agent_id: int | None = None
    risk_address: str | None = None
    notes: str | None = None


class PaymentCreate(BaseModel):
    policy_id: int
    due_date: date | None = None
    amount: float = Field(gt=0)
    paid_amount: float = Field(default=0, ge=0)
    currency: str = "LSL"
    method: str | None = None
    status: str = "Pending"
    transaction_reference: str | None = None
    paid_at: datetime | None = None


class LeadUpdate(BaseModel):
    stage: str | None = None
    priority: str | None = None
    assigned_to_id: int | None = None
    next_action_at: datetime | None = None
    notes: str | None = None


class ClaimUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_to_id: int | None = None
    claim_type: str | None = None
    reserve_amount: float | None = Field(default=None, ge=0)
    approved_amount: float | None = Field(default=None, ge=0)
    excess_amount: float | None = Field(default=None, ge=0)
    decision: str | None = None
    next_action_at: datetime | None = None
    notes: str | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=220)
    description: str | None = None
    entity_type: str | None = None
    entity_id: int | None = None
    assigned_to_id: int | None = None
    priority: str = "Normal"
    status: str = "Open"
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assigned_to_id: int | None = None
    priority: str | None = None
    status: str | None = None
    due_at: datetime | None = None


class StaffCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=180)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    role: str = "Viewer"
    department: str = "Operations"
    branch_id: int | None = None
    active: bool = True


class StaffUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    department: str | None = None
    branch_id: int | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)


class BranchCreate(BaseModel):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=140)
    location: str | None = None
    active: bool = True


class NoteCreate(BaseModel):
    entity_type: str = Field(min_length=2, max_length=40)
    entity_id: int
    body: str = Field(min_length=1, max_length=5000)


class SettingUpdate(BaseModel):
    value: str
    category: str = "General"
