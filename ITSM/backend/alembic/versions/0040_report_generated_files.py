"""报告增加生成文件字段：HTML/Word 报告加密落盘 /reports 目录。

Revision ID: 0040
Revises: 0039
"""
import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("report", sa.Column("html_filename", sa.String(255), nullable=True))
    op.add_column("report", sa.Column("docx_filename", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("report", "docx_filename")
    op.drop_column("report", "html_filename")
