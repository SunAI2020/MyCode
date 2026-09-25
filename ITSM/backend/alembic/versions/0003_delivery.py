"""项目交付：delivery

Revision ID: 0003
Revises: 0002
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("delivery")
