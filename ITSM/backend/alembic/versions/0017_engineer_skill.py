"""技能矩阵：engineer_skill

Revision ID: 0017
Revises: 0016
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("engineer_skill")
