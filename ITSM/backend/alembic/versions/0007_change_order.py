"""变更单：change_order

Revision ID: 0007
Revises: 0006
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("change_order")
