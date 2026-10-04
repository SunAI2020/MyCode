"""对既有库幂等授权：新菜单权限授予相应角色。

- deliveries / performance / reports → sys_ops、ticket_mgr
- reports → cust_admin、cust_service（客户角色只读本客户报告）

seed 的角色权限矩阵只在首次初始化时播种，既有库重跑 seed 不会把新菜单权限挂到已有角色上。
本迁移补齐这一步，纯数据操作、幂等（存在则跳过）。
注意：PostgreSQL 下 sa.text 的无类型参数会被推断为 text，与 varchar 列比较会报
「text versus character varying」，故对 code/name 显式 CAST(:x AS VARCHAR)。

Revision ID: 0034
Revises: 0033
"""
import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

PERMS = {
    "deliveries": "项目验收",
    "performance": "绩效考核",
    "reports": "报告中心",
}
GRANTS = {
    "sys_ops": ["deliveries", "performance", "reports"],
    "ticket_mgr": ["deliveries", "performance", "reports"],
    "cust_admin": ["reports"],
    "cust_service": ["reports"],
}


def upgrade() -> None:
    bind = op.get_bind()
    # 1. 幂等补权限点
    for code, name in PERMS.items():
        bind.execute(
            sa.text(
                "INSERT INTO sys_permission (code, name, type) "
                "SELECT CAST(:code AS VARCHAR), CAST(:name AS VARCHAR), 'menu' "
                "WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code = CAST(:code AS VARCHAR))"
            ),
            {"code": code, "name": name},
        )
    # 2. 幂等授权（角色不存在则自然跳过）
    for rcode, pcodes in GRANTS.items():
        for pcode in pcodes:
            bind.execute(
                sa.text(
                    "INSERT INTO sys_role_permission (role_id, permission_id) "
                    "SELECT r.id, p.id FROM sys_role r, sys_permission p "
                    "WHERE r.code = CAST(:rcode AS VARCHAR) AND p.code = CAST(:pcode AS VARCHAR) "
                    "AND NOT EXISTS (SELECT 1 FROM sys_role_permission rp "
                    "WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
                ),
                {"rcode": rcode, "pcode": pcode},
            )


def downgrade() -> None:
    bind = op.get_bind()
    for code in PERMS:
        bind.execute(
            sa.text(
                "DELETE FROM sys_role_permission WHERE permission_id IN "
                "(SELECT id FROM sys_permission WHERE code = CAST(:code AS VARCHAR))"
            ),
            {"code": code},
        )
        bind.execute(
            sa.text("DELETE FROM sys_permission WHERE code = CAST(:code AS VARCHAR)"),
            {"code": code},
        )
