"""工单状态调整：计划中→待派单、进行中→执行中、已验收→待结单。

工单状态由 待派单/待执行/执行中/待验收/已验收/已结单/已取消/已关闭 改为
待派单/待执行/执行中/待验收/待结单/已结单/已取消/已关闭，
旧值 已验收 归入 待结单，历史残留 计划中/进行中 一并回填。

Revision ID: 0037
Revises: 0036
"""
import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE work_order SET status = '待派单' WHERE status = '计划中'"))
    bind.execute(sa.text("UPDATE work_order SET status = '执行中' WHERE status = '进行中'"))
    bind.execute(sa.text("UPDATE work_order SET status = '待结单' WHERE status = '已验收'"))


def downgrade() -> None:
    # 多值合并为单值，无法可靠还原来源，降级不处理。
    pass
