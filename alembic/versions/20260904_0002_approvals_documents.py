"""Add approval workflow and document governance tables.

Revision ID: 20260904_0002
Revises: 20260904_0001
"""

from alembic import op
import sqlalchemy as sa

revision = "20260904_0002"
down_revision = "20260904_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    if "approval_requests" not in existing:
        op.create_table(
            "approval_requests",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("reference", sa.String(50), nullable=False, unique=True),
            sa.Column("workflow", sa.String(80), nullable=False),
            sa.Column("entity_type", sa.String(40), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("stage", sa.String(60), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("amount", sa.Float(), nullable=True),
            sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=False),
            sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True),
            sa.Column("decided_by_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("decision_notes", sa.Text(), nullable=True),
            sa.Column("requested_at", sa.DateTime(), nullable=False),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
        )
        for col in ("reference", "workflow", "entity_type", "entity_id", "stage", "status", "requested_by_id", "assigned_to_id"):
            op.create_index(f"ix_approval_requests_{col}", "approval_requests", [col])
    if "document_profiles" not in existing:
        op.create_table(
            "document_profiles",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("managed_documents.id"), nullable=False, unique=True),
            sa.Column("category", sa.String(80), nullable=False),
            sa.Column("document_status", sa.String(30), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("expiry_date", sa.Date(), nullable=True),
            sa.Column("checksum_sha256", sa.String(64), nullable=True),
            sa.Column("supersedes_document_id", sa.Integer(), sa.ForeignKey("managed_documents.id"), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        for col in ("document_id", "category", "document_status", "checksum_sha256"):
            op.create_index(f"ix_document_profiles_{col}", "document_profiles", [col])


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if "document_profiles" in existing:
        op.drop_table("document_profiles")
    if "approval_requests" in existing:
        op.drop_table("approval_requests")
