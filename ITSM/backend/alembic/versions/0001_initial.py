"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-25
"""

from alembic import op

from app.db.base import Base
import app.models  # noqa: F401  # 确保 18 张表注册进 Base.metadata

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MVP 阶段初始迁移：按当前模型元数据一次性建表（后续表结构变更再走增量迁移）
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
