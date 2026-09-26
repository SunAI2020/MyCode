"""外包账号隔离：outsource_user.user_id

Revision ID: 0012
Revises: 0011
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cols = [c["name"] for c in insp.get_columns("outsource_user")]
    if "user_id" not in cols:
        op.add_column(
            "outsource_user",
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("sys_user.id"), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("outsource_user", "user_id")
