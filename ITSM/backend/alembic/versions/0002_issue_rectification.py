"""问题整改闭环：issue / rectification / rectification_record

Revision ID: 0002
Revises: 0001
"""
from alembic import op

import app.models  # noqa: F401  触发模型注册
from app.db.base import Base

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 与 0001 相同策略：create_all 只补建尚不存在的表（3 张新表）
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("rectification_record")
    op.drop_table("rectification")
    op.drop_table("issue")
