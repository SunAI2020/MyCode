"""自助门户：work_order.description

Revision ID: 0010
Revises: 0009
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 幂等：fresh-from-scratch 时 0001 的 create_all 已按最新模型带出该列，此处仅对既有库补列
    insp = sa.inspect(op.get_bind())
    cols = [c["name"] for c in insp.get_columns("work_order")]
    if "description" not in cols:
        op.add_column("work_order", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("work_order", "description")
