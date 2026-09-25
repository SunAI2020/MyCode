"""知识库：kb_article

Revision ID: 0008
Revises: 0007
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("kb_article")
