from datetime import datetime, date
from sqlalchemy import String, Integer, DateTime, Date, Float, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    channel_user_id: Mapped[str] = mapped_column(String(120), index=True)
    channel: Mapped[str] = mapped_column(String(30), default="web")
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    state: Mapped[str] = mapped_column(String(80), default="choose_language")
    current_journey: Mapped[str | None] = mapped_column(String(40), nullable=True)
    context_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    holder_name: Mapped[str] = mapped_column(String(160))
    dob: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="Active")
    product: Mapped[str] = mapped_column(String(80))
    premium: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="LSL")


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(160))
    mobile: Mapped[str] = mapped_column(String(40))
    product: Mapped[str] = mapped_column(String(80))
    risk_json: Mapped[str] = mapped_column(Text, default="{}")
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="New")
    source: Mapped[str] = mapped_column(String(50), default="digital-assistant")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    policy_number: Mapped[str] = mapped_column(String(50), index=True)
    loss_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(220))
    estimated_damage: Mapped[float | None] = mapped_column(Float, nullable=True)
    contact: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default="Registered")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    attachments: Mapped[list["ClaimAttachment"]] = relationship(back_populates="claim", cascade="all, delete-orphan")


class ClaimAttachment(Base):
    __tablename__ = "claim_attachments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    claim: Mapped[Claim] = relationship(back_populates="attachments")


class AgentTicket(Base):
    __tablename__ = "agent_tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    reason: Mapped[str] = mapped_column(Text)
    queue: Mapped[str] = mapped_column(String(60), default="General support")
    language: Mapped[str] = mapped_column(String(10), default="en")
    status: Mapped[str] = mapped_column(String(30), default="Open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FAQArticle(Base):
    __tablename__ = "faq_articles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    question_en: Mapped[str] = mapped_column(String(240))
    answer_en: Mapped[str] = mapped_column(Text)
    question_st: Mapped[str] = mapped_column(String(240))
    answer_st: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
