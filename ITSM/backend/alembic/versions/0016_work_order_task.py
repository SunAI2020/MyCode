"""内部任务：work_order.task_type / deadline

Revision ID: 0016
Revises: 0015
"""
import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cols = [c["name"] for c in insp.get_columns("work_order")]
    if "task_type" not in cols:
        op.add_column("work_order", sa.Column("task_type", sa.String(32), nullable=True))
    if "deadline" not in cols:
        op.add_column("work_order", sa.Column("deadline", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("work_order", "deadline")
    op.drop_column("work_order", "task_type")
