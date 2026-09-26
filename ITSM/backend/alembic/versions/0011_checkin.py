"""移动端：check_in 签到打卡

Revision ID: 0011
Revises: 0010
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("check_in")
