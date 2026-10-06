"""合同/项目状态合并：已续约→已签约、已到期→已关闭。

项目状态由 洽谈中/执行中/已到期/已续约 改为
洽谈中/已签约/执行中/已验收/已结单/已关闭/已取消，
其中旧值 已续约 归入 已签约、已到期 归入 已关闭，此处做数据回填。

Revision ID: 0036
Revises: 0035
"""
import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE contract SET status = '已签约' WHERE status = '已续约'"))
    bind.execute(sa.text("UPDATE contract SET status = '已关闭' WHERE status = '已到期'"))


def downgrade() -> None:
    # 多值合并为单值，无法可靠还原来源，降级不处理。
    pass
