"""工单聚合：work_order.customer_id + 三张关联表

Revision ID: 0020
Revises: 0019
"""
import sqlalchemy as sa
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cols = [c["name"] for c in insp.get_columns("work_order")]
    if "customer_id" not in cols:
        op.add_column(
            "work_order",
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=True),
        )
        op.create_index("ix_work_order_customer_id", "work_order", ["customer_id"])
    # 三张聚合关联表（create_all 仅建缺失表，幂等）
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("work_order_cycle")
    op.drop_table("work_order_item")
    op.drop_table("work_order_ci")
    op.drop_index("ix_work_order_customer_id", table_name="work_order")
    op.drop_column("work_order", "customer_id")
