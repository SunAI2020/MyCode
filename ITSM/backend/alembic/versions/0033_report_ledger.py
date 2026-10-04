"""报告台账表。

Revision ID: 0033
Revises: 0032
"""
import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("report_type", sa.String(32), nullable=False, server_default="运维报告"),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contract.id"), nullable=True),
        sa.Column("work_order_id", sa.Integer(), sa.ForeignKey("work_order.id"), nullable=True),
        sa.Column("report_no", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="草稿"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_report_customer_id", "report", ["customer_id"])
    op.create_index("ix_report_contract_id", "report", ["contract_id"])
    op.create_index("ix_report_work_order_id", "report", ["work_order_id"])


def downgrade() -> None:
    op.drop_table("report")
