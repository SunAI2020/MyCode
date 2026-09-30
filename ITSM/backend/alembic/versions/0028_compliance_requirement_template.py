"""合规运营框架：监管要求模板库。

新增 compliance_requirement_template 全局监管要求模板表（等保2.0 / 密码测评 / 数据安全 / 公安部176号令），
按客户「应用模板」实例化为合规要求（compliance_requirement）。

Revision ID: 0028
Revises: 0027
"""
import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "compliance_requirement_template" not in insp.get_table_names():
        op.create_table(
            "compliance_requirement_template",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("reg_source", sa.String(32), nullable=False),  # 等保2.0/密码测评/数据安全/公安部176号令
            sa.Column("domain", sa.String(64), nullable=False),  # 标准领域，如 安全物理环境/数据分类分级
            sa.Column("title", sa.String(128), nullable=False),  # 条款标题
            sa.Column("clause", sa.Text(), nullable=False),  # 要求原文
            sa.Column("category", sa.String(16), nullable=False, server_default="技术"),  # 技术/组织/制度/台账/流程
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.create_index(
            "ix_compliance_requirement_template_reg_source",
            "compliance_requirement_template",
            ["reg_source"],
        )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "compliance_requirement_template" in insp.get_table_names():
        op.drop_index("ix_compliance_requirement_template_reg_source", table_name="compliance_requirement_template")
        op.drop_table("compliance_requirement_template")
