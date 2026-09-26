"""工作流审批流：approval

Revision ID: 0013
Revises: 0012
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("approval")
