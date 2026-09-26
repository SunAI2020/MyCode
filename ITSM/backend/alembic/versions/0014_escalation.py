"""SLA 升级记录：escalation

Revision ID: 0014
Revises: 0013
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("escalation")
