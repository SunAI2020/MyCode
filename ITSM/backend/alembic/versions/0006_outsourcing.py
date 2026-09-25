"""外包协作：outsource_user / outsourcing / outsourcing_report

Revision ID: 0006
Revises: 0005
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("outsourcing_report")
    op.drop_table("outsourcing")
    op.drop_table("outsource_user")
