"""客户表增加 status 字段（合作中/已终止）。

Revision ID: 0039
Revises: 0038
"""
import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customer", sa.Column("status", sa.String(16), nullable=False, server_default="合作中"))


def downgrade() -> None:
    op.drop_column("customer", "status")
