"""驻场服务：onsite_service / onsite_daily_report

Revision ID: 0005
Revises: 0004
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("onsite_daily_report")
    op.drop_table("onsite_service")
