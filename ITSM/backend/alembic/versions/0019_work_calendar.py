"""工作日历：work_calendar

Revision ID: 0019
Revises: 0018
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("work_calendar")
