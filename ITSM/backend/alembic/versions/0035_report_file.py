"""报告文件存储：原始文件加密入库 + 脱敏文本。

Revision ID: 0035
Revises: 0034
"""
import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("report", sa.Column("original_filename", sa.String(255), nullable=True))
    op.add_column("report", sa.Column("mime_type", sa.String(128), nullable=True))
    op.add_column("report", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("report", sa.Column("file_hash", sa.String(64), nullable=True))
    op.add_column("report", sa.Column("content_enc", sa.LargeBinary(), nullable=True))
    op.add_column("report", sa.Column("masked_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("report", "masked_text")
    op.drop_column("report", "content_enc")
    op.drop_column("report", "file_hash")
    op.drop_column("report", "file_size")
    op.drop_column("report", "mime_type")
    op.drop_column("report", "original_filename")
