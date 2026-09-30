"""合规运营框架：新增 4 张合规台账表 + issue 挂接合规要求。

步骤 51（安全服务 3.0 合规运营理念落地 · P1 合规底座）。
- 新增 compliance_requirement / compliance_evidence / compliance_check / duty_report；
- issue 新增 requirement_id（可空），打通「合规缺口 → 问题 → 整改 → 核验」闭环。

Revision ID: 0026
Revises: 0025
"""
import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    existing = insp.get_table_names()

    if "compliance_requirement" not in existing:
        op.create_table(
            "compliance_requirement",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("contract.id"), nullable=True),
            sa.Column("source_type", sa.String(16), nullable=False, server_default="监管"),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("clause", sa.Text(), nullable=False),
            sa.Column("category", sa.String(16), nullable=False, server_default="技术"),
            sa.Column("reg_source", sa.String(64), nullable=True),
            sa.Column("status", sa.String(8), nullable=False, server_default="启用"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_compliance_requirement_customer_id", "compliance_requirement", ["customer_id"])
        op.create_index("ix_compliance_requirement_project_id", "compliance_requirement", ["project_id"])

    if "compliance_evidence" not in existing:
        op.create_table(
            "compliance_evidence",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("compliance_requirement.id"), nullable=False),
            sa.Column("source_type", sa.String(16), nullable=False, server_default="人工"),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("evidence_type", sa.String(8), nullable=False, server_default="自动"),
            sa.Column("file_ref", sa.String(255), nullable=True),
            sa.Column("content_hash", sa.String(64), nullable=True),
            sa.Column("operator_id", sa.Integer(), sa.ForeignKey("sys_user.id"), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_compliance_evidence_requirement_id", "compliance_evidence", ["requirement_id"])

    if "compliance_check" not in existing:
        op.create_table(
            "compliance_check",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("compliance_requirement.id"), nullable=False),
            sa.Column("check_type", sa.String(16), nullable=False, server_default="巡查"),
            sa.Column("status", sa.String(16), nullable=False, server_default="未覆盖"),
            sa.Column("result", sa.String(8), nullable=True),
            sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issue.id"), nullable=True),
            sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("compliance_evidence.id"), nullable=True),
            sa.Column("assignee", sa.Integer(), nullable=True),
            sa.Column("check_date", sa.Date(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_compliance_check_requirement_id", "compliance_check", ["requirement_id"])

    if "duty_report" not in existing:
        op.create_table(
            "duty_report",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("contract.id"), nullable=True),
            sa.Column("period_start", sa.Date(), nullable=True),
            sa.Column("period_end", sa.Date(), nullable=True),
            sa.Column("status", sa.String(8), nullable=False, server_default="草稿"),
            sa.Column("content_json", sa.Text(), nullable=True),
            sa.Column("file_ref", sa.String(255), nullable=True),
            sa.Column("sign", sa.String(16), nullable=False, server_default="未签署"),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("sys_user.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_duty_report_customer_id", "duty_report", ["customer_id"])
        op.create_index("ix_duty_report_project_id", "duty_report", ["project_id"])

    # issue 挂接合规要求（可空）
    issue_cols = {c["name"] for c in insp.get_columns("issue")}
    if "requirement_id" not in issue_cols:
        op.add_column(
            "issue",
            sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("compliance_requirement.id"), nullable=True),
        )
        op.create_index("ix_issue_requirement_id", "issue", ["requirement_id"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())

    issue_cols = {c["name"] for c in insp.get_columns("issue")}
    if "requirement_id" in issue_cols:
        op.drop_index("ix_issue_requirement_id", table_name="issue")
        op.drop_column("issue", "requirement_id")

    op.drop_table("duty_report")
    op.drop_table("compliance_check")
    op.drop_table("compliance_evidence")
    op.drop_table("compliance_requirement")
