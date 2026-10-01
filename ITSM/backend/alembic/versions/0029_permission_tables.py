"""权限表兜底：sys_permission / sys_role_permission。

0001 的 create_all 已按模型建表；本迁移对既有库幂等补建（防止旧库因历史 create_all 时点缺失）。
权限点与角色默认矩阵由 app.db.seed 播种（幂等）。

Revision ID: 0029
Revises: 0028
"""
import sqlalchemy as sa
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "sys_role_permission" in insp.get_table_names():
        op.drop_table("sys_role_permission")
    if "sys_permission" in insp.get_table_names():
        op.drop_table("sys_permission")
