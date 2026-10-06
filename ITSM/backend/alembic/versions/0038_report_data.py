"""报告台账增加 report_data 字段：结构化报告内容（工作内容/安全问题统计/详情）JSON 文本。

Revision ID: 0038
Revises: 0037
"""
import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("report", sa.Column("report_data", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("report", "report_data")
