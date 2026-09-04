from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class UnderwritingQuote(Base):
    __tablename__ = "underwriting_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("insurance_products.id"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), nullable=True, index=True)
    underwriter_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), nullable=True, index=True)
    converted_policy_id: Mapped[int | None] = mapped_column(ForeignKey("policies.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Quoted", index=True)
    sum_insured: Mapped[float] = mapped_column(Float, default=0.0)
    excess_amount: Mapped[float] = mapped_column(Float, default=0.0)
    risk_json: Mapped[str] = mapped_column(Text, default="{}")
    base_premium: Mapped[float] = mapped_column(Float, default=0.0)
    loading_amount: Mapped[float] = mapped_column(Float, default=0.0)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total_premium: Mapped[float] = mapped_column(Float, default=0.0)
    referral_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PolicyTransaction(Base):
    __tablename__ = "policy_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"), index=True)
    transaction_type: Mapped[str] = mapped_column(String(40), index=True)
    effective_date: Mapped[date] = mapped_column(Date)
    previous_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    premium_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    premium_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    sum_insured_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    sum_insured_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ClaimActivity(Base):
    __tablename__ = "claim_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    activity_type: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ClaimSettlement(Base):
    __tablename__ = "claim_settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    reference: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    amount: Mapped[float] = mapped_column(Float)
    payment_type: Mapped[str] = mapped_column(String(40), default="Settlement")
    status: Mapped[str] = mapped_column(String(30), default="Approved", index=True)
    payment_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CustomerKYC(Base):
    __tablename__ = "customer_kyc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), unique=True, index=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="Pending", index=True)
    identity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    identity_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    proof_of_address_status: Mapped[str] = mapped_column(String(30), default="Pending")
    pep_status: Mapped[str] = mapped_column(String(30), default="Not Assessed")
    sanctions_status: Mapped[str] = mapped_column(String(30), default="Not Assessed")
    risk_rating: Mapped[str] = mapped_column(String(20), default="Normal", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Intermediary(Base):
    __tablename__ = "intermediaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    intermediary_type: Mapped[str] = mapped_column(String(40), default="Agent", index=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    commission_rate: Mapped[float] = mapped_column(Float, default=0.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PolicyIntermediary(Base):
    __tablename__ = "policy_intermediaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"), unique=True, index=True)
    intermediary_id: Mapped[int] = mapped_column(ForeignKey("intermediaries.id"), index=True)
    commission_rate: Mapped[float] = mapped_column(Float, default=0.0)
    earned_commission: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    workflow: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    stage: Mapped[str] = mapped_column(String(60), default="Review", index=True)
    status: Mapped[str] = mapped_column(String(30), default="Pending", index=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("staff_users.id"), index=True)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), nullable=True, index=True)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DocumentProfile(Base):
    __tablename__ = "document_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("managed_documents.id"), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(80), default="General", index=True)
    document_status: Mapped[str] = mapped_column(String(30), default="Current", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    supersedes_document_id: Mapped[int | None] = mapped_column(ForeignKey("managed_documents.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
