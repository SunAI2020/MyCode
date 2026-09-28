"""合同原件导入：Contract 新增 5 列 + 新增 contract_archive 表。

步骤 49。Contract 新增 sign_date/staff_requirement/accept_standard/delivery_docs/
acceptance_report_format；contract_archive 存原件元数据（文件加密落盘）与提取字段 JSON。

Revision ID: 0022
Revises: 0021
"""
import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

_CONTRACT_NEW_COLS = [
    ("sign_date", sa.Date()),
    ("staff_requirement", sa.Text()),
    ("accept_standard", sa.Text()),
    ("delivery_docs", sa.Text()),
    ("acceptance_report_format", sa.Text()),
]


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    cols = {c["name"] for c in insp.get_columns("contract")}
    for name, typ in _CONTRACT_NEW_COLS:
        if name not in cols:
            op.add_column("contract", sa.Column(name, typ, nullable=True))

    if "contract_archive" not in insp.get_table_names():
        op.create_table(
            "contract_archive",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contract.id"), nullable=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=True),
            sa.Column("original_filename", sa.String(255), nullable=False),
            sa.Column("stored_name", sa.String(128), nullable=False),
            sa.Column("file_hash", sa.String(64), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("mime_type", sa.String(64), nullable=False),
            sa.Column("extracted", sa.Text(), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="待确认"),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("sys_user.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_contract_archive_contract_id", "contract_archive", ["contract_id"])
        op.create_index("ix_contract_archive_customer_id", "contract_archive", ["customer_id"])


def downgrade() -> None:
    op.drop_table("contract_archive")
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("contract")}
    for name, _ in _CONTRACT_NEW_COLS:
        if name in cols:
            op.drop_column("contract", name)
