"""工作流引擎：workflow_rule / action_log

Revision ID: 0009
Revises: 0008
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("action_log")
    op.drop_table("workflow_rule")
