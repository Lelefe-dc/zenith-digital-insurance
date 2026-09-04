"""Baseline existing Zenith schema and add core insurance tables.

Revision ID: 20260904_0001
Revises:
Create Date: 2026-09-04

This baseline is intentionally idempotent for existing deployments: SQLAlchemy
creates only tables that are missing, allowing Alembic to adopt databases that
were originally created with Base.metadata.create_all(). Future revisions should
use explicit Alembic operations.
"""

from alembic import op

from app.database import Base

import app.models  # noqa: F401
import app.management_models  # noqa: F401
import app.core_models  # noqa: F401
import app.management_extras  # noqa: F401

revision = "20260904_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Baseline downgrade is deliberately non-destructive because this revision
    # adopts pre-existing production/development databases.
    pass
