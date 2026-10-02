"""术语统一：服务项目 → 服务类别。

compliance_requirement.source_type 枚举值「服务项目」改名为「服务类别」（与界面/代码术语对齐）。

Revision ID: 0032
Revises: 0031
"""
import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    t = sa.table("compliance_requirement", sa.column("source_type", sa.String(16)))
    op.execute(t.update().where(t.c.source_type == "服务项目").values(source_type="服务类别"))


def downgrade() -> None:
    t = sa.table("compliance_requirement", sa.column("source_type", sa.String(16)))
    op.execute(t.update().where(t.c.source_type == "服务类别").values(source_type="服务项目"))
