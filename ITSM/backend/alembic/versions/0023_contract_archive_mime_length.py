"""合同原件 mime_type 列加宽：docx 标准 MIME（71 字符）超出原 64 导致上传 500。

Revision ID: 0023
Revises: 0022
"""
import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "contract_archive",
        "mime_type",
        existing_type=sa.String(64),
        type_=sa.String(128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "contract_archive",
        "mime_type",
        existing_type=sa.String(128),
        type_=sa.String(64),
        existing_nullable=False,
    )
