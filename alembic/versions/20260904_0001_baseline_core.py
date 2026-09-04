"""Baseline Zenith schema and core insurance tables.

Revision ID: 20260904_0001
Revises:
Create Date: 2026-09-04

The snapshot below is intentionally self-contained rather than importing live
application model metadata. This makes the baseline deterministic for future
fresh installations while still adopting existing databases safely via
checkfirst=True.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260904_0001"
down_revision = None
branch_labels = None
depends_on = None

metadata = sa.MetaData()


def T(name, *columns):
    return sa.Table(name, metadata, *columns)


T("conversation_sessions",
  sa.Column("id", sa.String(36), primary_key=True),
  sa.Column("channel_user_id", sa.String(120), nullable=False, index=True),
  sa.Column("channel", sa.String(30), nullable=False),
  sa.Column("language", sa.String(10), nullable=True),
  sa.Column("state", sa.String(80), nullable=False),
  sa.Column("current_journey", sa.String(40), nullable=True),
  sa.Column("context_json", sa.Text(), nullable=False),
  sa.Column("status", sa.String(30), nullable=False),
  sa.Column("created_at", sa.DateTime(), nullable=False),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("policies",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("policy_number", sa.String(50), nullable=False, unique=True, index=True),
  sa.Column("holder_name", sa.String(160), nullable=False),
  sa.Column("dob", sa.Date(), nullable=False),
  sa.Column("status", sa.String(30), nullable=False),
  sa.Column("product", sa.String(80), nullable=False),
  sa.Column("premium", sa.Float(), nullable=False),
  sa.Column("currency", sa.String(10), nullable=False))

T("leads",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("reference", sa.String(40), nullable=False, unique=True, index=True),
  sa.Column("session_id", sa.String(36), nullable=False, index=True),
  sa.Column("name", sa.String(160), nullable=False),
  sa.Column("mobile", sa.String(40), nullable=False),
  sa.Column("product", sa.String(80), nullable=False),
  sa.Column("risk_json", sa.Text(), nullable=False),
  sa.Column("consent", sa.Boolean(), nullable=False),
  sa.Column("status", sa.String(30), nullable=False),
  sa.Column("source", sa.String(50), nullable=False),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("claims",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("reference", sa.String(40), nullable=False, unique=True, index=True),
  sa.Column("session_id", sa.String(36), nullable=False, index=True),
  sa.Column("policy_number", sa.String(50), nullable=False, index=True),
  sa.Column("loss_date", sa.Date(), nullable=False),
  sa.Column("description", sa.Text(), nullable=False),
  sa.Column("location", sa.String(220), nullable=False),
  sa.Column("estimated_damage", sa.Float(), nullable=True),
  sa.Column("contact", sa.String(60), nullable=False),
  sa.Column("status", sa.String(30), nullable=False),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("claim_attachments",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False, index=True),
  sa.Column("filename", sa.String(255), nullable=False),
  sa.Column("stored_path", sa.String(500), nullable=False),
  sa.Column("mime_type", sa.String(120), nullable=False),
  sa.Column("size_bytes", sa.Integer(), nullable=False),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("agent_tickets",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("reference", sa.String(40), nullable=False, unique=True, index=True),
  sa.Column("session_id", sa.String(36), nullable=False, index=True),
  sa.Column("reason", sa.Text(), nullable=False),
  sa.Column("queue", sa.String(60), nullable=False),
  sa.Column("language", sa.String(10), nullable=False),
  sa.Column("status", sa.String(30), nullable=False),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("faq_articles",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("category", sa.String(80), nullable=False, index=True),
  sa.Column("question_en", sa.String(240), nullable=False),
  sa.Column("answer_en", sa.Text(), nullable=False),
  sa.Column("question_st", sa.String(240), nullable=False),
  sa.Column("answer_st", sa.Text(), nullable=False),
  sa.Column("active", sa.Boolean(), nullable=False))

T("audit_events",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("session_id", sa.String(36), nullable=True, index=True),
  sa.Column("event_type", sa.String(80), nullable=False, index=True),
  sa.Column("payload_json", sa.Text(), nullable=False),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("branches",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("code", sa.String(30), nullable=False, unique=True, index=True),
  sa.Column("name", sa.String(140), nullable=False),
  sa.Column("location", sa.String(220), nullable=True),
  sa.Column("active", sa.Boolean(), nullable=False),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("customers",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("customer_number", sa.String(40), nullable=False, unique=True, index=True),
  sa.Column("full_name", sa.String(180), nullable=False, index=True),
  sa.Column("national_id", sa.String(80), nullable=True, index=True),
  sa.Column("date_of_birth", sa.Date(), nullable=True),
  sa.Column("mobile", sa.String(50), nullable=False, index=True),
  sa.Column("email", sa.String(180), nullable=True, index=True),
  sa.Column("address", sa.String(300), nullable=True),
  sa.Column("district", sa.String(100), nullable=True),
  sa.Column("occupation", sa.String(140), nullable=True),
  sa.Column("status", sa.String(30), nullable=False, index=True),
  sa.Column("source", sa.String(60), nullable=False),
  sa.Column("created_at", sa.DateTime(), nullable=False),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("insurance_products",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("code", sa.String(40), nullable=False, unique=True, index=True),
  sa.Column("name", sa.String(160), nullable=False, index=True),
  sa.Column("category", sa.String(100), nullable=False, index=True),
  sa.Column("description", sa.Text(), nullable=True),
  sa.Column("base_premium", sa.Float(), nullable=False),
  sa.Column("currency", sa.String(10), nullable=False),
  sa.Column("active", sa.Boolean(), nullable=False),
  sa.Column("created_at", sa.DateTime(), nullable=False),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("staff_users",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("employee_number", sa.String(40), nullable=False, unique=True, index=True),
  sa.Column("full_name", sa.String(180), nullable=False),
  sa.Column("email", sa.String(180), nullable=False, unique=True, index=True),
  sa.Column("password_hash", sa.String(300), nullable=False),
  sa.Column("role", sa.String(40), nullable=False, index=True),
  sa.Column("department", sa.String(100), nullable=False),
  sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True, index=True),
  sa.Column("active", sa.Boolean(), nullable=False),
  sa.Column("last_login_at", sa.DateTime(), nullable=True),
  sa.Column("created_at", sa.DateTime(), nullable=False),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("management_sessions",
  sa.Column("id", sa.String(36), primary_key=True),
  sa.Column("user_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=False, index=True),
  sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
  sa.Column("expires_at", sa.DateTime(), nullable=False, index=True),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("policy_profiles",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("policy_id", sa.Integer(), sa.ForeignKey("policies.id"), nullable=False, unique=True, index=True),
  sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False, index=True),
  sa.Column("product_id", sa.Integer(), sa.ForeignKey("insurance_products.id"), nullable=True, index=True),
  sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True, index=True),
  sa.Column("agent_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True, index=True),
  sa.Column("effective_date", sa.Date(), nullable=False),
  sa.Column("expiry_date", sa.Date(), nullable=True),
  sa.Column("sum_insured", sa.Float(), nullable=True),
  sa.Column("payment_frequency", sa.String(30), nullable=False),
  sa.Column("payment_status", sa.String(30), nullable=False, index=True),
  sa.Column("risk_address", sa.String(300), nullable=True),
  sa.Column("notes", sa.Text(), nullable=True),
  sa.Column("created_at", sa.DateTime(), nullable=False),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("premium_payments",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("reference", sa.String(50), nullable=False, unique=True, index=True),
  sa.Column("policy_id", sa.Integer(), sa.ForeignKey("policies.id"), nullable=False, index=True),
  sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True, index=True),
  sa.Column("due_date", sa.Date(), nullable=True),
  sa.Column("amount", sa.Float(), nullable=False),
  sa.Column("paid_amount", sa.Float(), nullable=False),
  sa.Column("currency", sa.String(10), nullable=False),
  sa.Column("method", sa.String(50), nullable=True),
  sa.Column("status", sa.String(30), nullable=False, index=True),
  sa.Column("transaction_reference", sa.String(100), nullable=True),
  sa.Column("paid_at", sa.DateTime(), nullable=True),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("lead_profiles",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False, unique=True, index=True),
  sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True, index=True),
  sa.Column("stage", sa.String(40), nullable=False, index=True),
  sa.Column("priority", sa.String(20), nullable=False),
  sa.Column("next_action_at", sa.DateTime(), nullable=True),
  sa.Column("notes", sa.Text(), nullable=True),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("claim_profiles",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False, unique=True, index=True),
  sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True, index=True),
  sa.Column("priority", sa.String(20), nullable=False, index=True),
  sa.Column("claim_type", sa.String(80), nullable=True),
  sa.Column("reserve_amount", sa.Float(), nullable=False),
  sa.Column("approved_amount", sa.Float(), nullable=False),
  sa.Column("excess_amount", sa.Float(), nullable=False),
  sa.Column("decision", sa.String(40), nullable=True),
  sa.Column("next_action_at", sa.DateTime(), nullable=True),
  sa.Column("closed_at", sa.DateTime(), nullable=True),
  sa.Column("notes", sa.Text(), nullable=True),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("work_tasks",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("reference", sa.String(50), nullable=False, unique=True, index=True),
  sa.Column("title", sa.String(220), nullable=False),
  sa.Column("description", sa.Text(), nullable=True),
  sa.Column("entity_type", sa.String(40), nullable=True, index=True),
  sa.Column("entity_id", sa.Integer(), nullable=True, index=True),
  sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True, index=True),
  sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True),
  sa.Column("priority", sa.String(20), nullable=False, index=True),
  sa.Column("status", sa.String(30), nullable=False, index=True),
  sa.Column("due_at", sa.DateTime(), nullable=True),
  sa.Column("completed_at", sa.DateTime(), nullable=True),
  sa.Column("created_at", sa.DateTime(), nullable=False),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("case_notes",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("entity_type", sa.String(40), nullable=False, index=True),
  sa.Column("entity_id", sa.Integer(), nullable=False, index=True),
  sa.Column("author_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True),
  sa.Column("body", sa.Text(), nullable=False),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("managed_documents",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("entity_type", sa.String(40), nullable=False, index=True),
  sa.Column("entity_id", sa.Integer(), nullable=False, index=True),
  sa.Column("filename", sa.String(255), nullable=False),
  sa.Column("stored_path", sa.String(500), nullable=False),
  sa.Column("mime_type", sa.String(120), nullable=False),
  sa.Column("size_bytes", sa.Integer(), nullable=False),
  sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("system_settings",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("key", sa.String(120), nullable=False, unique=True, index=True),
  sa.Column("value", sa.Text(), nullable=False),
  sa.Column("category", sa.String(80), nullable=False),
  sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("service_ticket_profiles",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("agent_tickets.id"), nullable=False, unique=True, index=True),
  sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True, index=True),
  sa.Column("priority", sa.String(20), nullable=False, index=True),
  sa.Column("notes", sa.Text(), nullable=True),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("underwriting_quotes",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("reference", sa.String(50), nullable=False, unique=True, index=True),
  sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True, index=True),
  sa.Column("product_id", sa.Integer(), sa.ForeignKey("insurance_products.id"), nullable=False, index=True),
  sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True, index=True),
  sa.Column("underwriter_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True, index=True),
  sa.Column("converted_policy_id", sa.Integer(), sa.ForeignKey("policies.id"), nullable=True, index=True),
  sa.Column("status", sa.String(30), nullable=False, index=True),
  sa.Column("sum_insured", sa.Float(), nullable=False),
  sa.Column("excess_amount", sa.Float(), nullable=False),
  sa.Column("risk_json", sa.Text(), nullable=False),
  sa.Column("base_premium", sa.Float(), nullable=False),
  sa.Column("loading_amount", sa.Float(), nullable=False),
  sa.Column("discount_amount", sa.Float(), nullable=False),
  sa.Column("tax_amount", sa.Float(), nullable=False),
  sa.Column("total_premium", sa.Float(), nullable=False),
  sa.Column("referral_reason", sa.Text(), nullable=True),
  sa.Column("decision_notes", sa.Text(), nullable=True),
  sa.Column("valid_until", sa.Date(), nullable=True),
  sa.Column("created_at", sa.DateTime(), nullable=False),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("policy_transactions",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("policy_id", sa.Integer(), sa.ForeignKey("policies.id"), nullable=False, index=True),
  sa.Column("transaction_type", sa.String(40), nullable=False, index=True),
  sa.Column("effective_date", sa.Date(), nullable=False),
  sa.Column("previous_status", sa.String(30), nullable=True),
  sa.Column("new_status", sa.String(30), nullable=True),
  sa.Column("premium_before", sa.Float(), nullable=True),
  sa.Column("premium_after", sa.Float(), nullable=True),
  sa.Column("sum_insured_before", sa.Float(), nullable=True),
  sa.Column("sum_insured_after", sa.Float(), nullable=True),
  sa.Column("reason", sa.Text(), nullable=True),
  sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True, index=True),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("claim_activities",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False, index=True),
  sa.Column("activity_type", sa.String(60), nullable=False, index=True),
  sa.Column("status", sa.String(40), nullable=True),
  sa.Column("amount", sa.Float(), nullable=True),
  sa.Column("notes", sa.Text(), nullable=True),
  sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True, index=True),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("claim_settlements",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False, index=True),
  sa.Column("reference", sa.String(50), nullable=False, unique=True, index=True),
  sa.Column("amount", sa.Float(), nullable=False),
  sa.Column("payment_type", sa.String(40), nullable=False),
  sa.Column("status", sa.String(30), nullable=False, index=True),
  sa.Column("payment_reference", sa.String(120), nullable=True),
  sa.Column("paid_at", sa.DateTime(), nullable=True),
  sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True, index=True),
  sa.Column("created_at", sa.DateTime(), nullable=False))

T("customer_kyc",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False, unique=True, index=True),
  sa.Column("verification_status", sa.String(30), nullable=False, index=True),
  sa.Column("identity_type", sa.String(50), nullable=True),
  sa.Column("identity_number", sa.String(100), nullable=True, index=True),
  sa.Column("proof_of_address_status", sa.String(30), nullable=False),
  sa.Column("pep_status", sa.String(30), nullable=False),
  sa.Column("sanctions_status", sa.String(30), nullable=False),
  sa.Column("risk_rating", sa.String(20), nullable=False, index=True),
  sa.Column("notes", sa.Text(), nullable=True),
  sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True),
  sa.Column("reviewed_at", sa.DateTime(), nullable=True),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("intermediaries",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("code", sa.String(40), nullable=False, unique=True, index=True),
  sa.Column("name", sa.String(180), nullable=False, index=True),
  sa.Column("intermediary_type", sa.String(40), nullable=False, index=True),
  sa.Column("email", sa.String(180), nullable=True),
  sa.Column("mobile", sa.String(50), nullable=True),
  sa.Column("commission_rate", sa.Float(), nullable=False),
  sa.Column("active", sa.Boolean(), nullable=False),
  sa.Column("created_at", sa.DateTime(), nullable=False),
  sa.Column("updated_at", sa.DateTime(), nullable=False))

T("policy_intermediaries",
  sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
  sa.Column("policy_id", sa.Integer(), sa.ForeignKey("policies.id"), nullable=False, unique=True, index=True),
  sa.Column("intermediary_id", sa.Integer(), sa.ForeignKey("intermediaries.id"), nullable=False, index=True),
  sa.Column("commission_rate", sa.Float(), nullable=False),
  sa.Column("earned_commission", sa.Float(), nullable=False),
  sa.Column("created_at", sa.DateTime(), nullable=False),
  sa.Column("updated_at", sa.DateTime(), nullable=False))


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Baseline adoption is deliberately non-destructive.
    pass
