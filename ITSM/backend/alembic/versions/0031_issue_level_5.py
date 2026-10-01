"""隐患分级扩展：issue.level 从 3 级映射到 5 级（CVE/CVSS）。

高→高危、中→中危、低→低危；新增「严重」「信息」两档由新数据使用。

Revision ID: 0031
Revises: 0030
"""
import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    t = sa.table("issue", sa.column("level", sa.String(8)))
    for old, new in (("高", "高危"), ("中", "中危"), ("低", "低危")):
        op.execute(t.update().where(t.c.level == old).values(level=new))


def downgrade() -> None:
    t = sa.table("issue", sa.column("level", sa.String(8)))
    for old, new in (("高危", "高"), ("中危", "中"), ("低危", "低")):
        op.execute(t.update().where(t.c.level == old).values(level=new))
