"""contract_item.ci_id 允许为空（服务项目不针对具体系统，记作「//」）。

Revision ID: 0025
Revises: 0024
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("contract_item", "ci_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("contract_item", "ci_id", existing_type=sa.Integer(), nullable=False)
