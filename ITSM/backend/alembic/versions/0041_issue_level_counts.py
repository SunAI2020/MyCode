"""问题增加 level_counts 字段：报告安全问题统计按级别数量落库。

Revision ID: 0041
Revises: 0040
"""
import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("issue", sa.Column("level_counts", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("issue", "level_counts")
