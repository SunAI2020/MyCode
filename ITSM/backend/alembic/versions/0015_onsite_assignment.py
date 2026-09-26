"""驻场人员清单：onsite_assignment

Revision ID: 0015
Revises: 0014
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("onsite_assignment")
