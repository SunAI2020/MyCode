"""权限矩阵去重约束：sys_role_permission 加 (role_id, permission_id) 唯一索引。

配合 update_role_permissions 的入参去重，防止重复权限点 code 写入重复行。

Revision ID: 0030
Revises: 0029
"""
import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    names = {i["name"] for i in insp.get_indexes("sys_role_permission")}
    if "uq_sys_role_permission_role_perm" not in names:
        op.create_index(
            "uq_sys_role_permission_role_perm",
            "sys_role_permission",
            ["role_id", "permission_id"],
            unique=True,
        )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    names = {i["name"] for i in insp.get_indexes("sys_role_permission")}
    if "uq_sys_role_permission_role_perm" in names:
        op.drop_index("uq_sys_role_permission_role_perm", table_name="sys_role_permission")
