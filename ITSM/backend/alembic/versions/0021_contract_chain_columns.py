"""补齐步骤 47 主从链路列：cmdb_ci.contract_id + contract_item.ci_id NOT NULL

步骤 47 的「服务对象挂合同 / 服务项目挂服务对象」改动了模型，但当时走的是
数据库重置（清空重建）而非增量迁移，故存量库 upgrade 到此会缺这两处结构。
本迁移幂等补齐；存量库历史行的 NULL 归属无法干净回填，建议对旧数据执行重置
（DROP SCHEMA public CASCADE + alembic upgrade head + app.db.seed）。

Revision ID: 0021
Revises: 0020
"""
import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    # cmdb_ci.contract_id（历史行无合同归属，允许 NULL；新数据由 API 强制填）
    cols = [c["name"] for c in insp.get_columns("cmdb_ci")]
    if "contract_id" not in cols:
        op.add_column(
            "cmdb_ci",
            sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contract.id"), nullable=True),
        )
        op.create_index("ix_cmdb_ci_contract_id", "cmdb_ci", ["contract_id"])

    # contract_item.ci_id 由可空改为 NOT NULL（历史 NULL 行会阻止此处，需先清理/重置）
    ci_cols = [c for c in insp.get_columns("contract_item") if c["name"] == "ci_id"]
    if ci_cols and ci_cols[0]["nullable"]:
        op.alter_column("contract_item", "ci_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    op.drop_index("ix_cmdb_ci_contract_id", table_name="cmdb_ci")
    op.drop_column("cmdb_ci", "contract_id")
