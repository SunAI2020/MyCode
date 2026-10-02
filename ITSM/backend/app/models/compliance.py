"""合规运营框架模型：合规要求 / 合规证据 / 合规核验 / 履职报告。

步骤 51（安全服务 3.0 合规运营理念落地）。合规台账框架：把现有散点留痕
（工单/整改/变更/交付/审批/审计）统一映射为「合规要求 → 履约证据 → 履职报告」。
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ComplianceRequirement(Base):
    """合规要求（底座）：监管要求 / 合同义务 / 服务类别义务条目化。"""

    __tablename__ = "compliance_requirement"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), index=True)  # 冗余，行级隔离
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("contract.id"), nullable=True, index=True
    )  # 归属项目；null = 全局监管要求
    source_type: Mapped[str] = mapped_column(String(16), default="监管")  # 监管/合同义务/服务类别
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 指向 contract / contract_item
    clause: Mapped[str] = mapped_column(Text)  # 条款原文 / 要求描述
    category: Mapped[str] = mapped_column(String(16), default="技术")  # 技术/组织/制度/台账/流程
    reg_source: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 出处：176号令/等保2.0/…
    status: Mapped[str] = mapped_column(String(8), default="启用")  # 启用/停用
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ComplianceEvidence(Base):
    """合规证据（留痕链）：自动采集 + 人工上传，带内容哈希防篡改。"""

    __tablename__ = "compliance_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("compliance_requirement.id"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(16), default="人工")  # 工单/整改/变更/交付/审批/审计/人工
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 指向现有实体 id
    evidence_type: Mapped[str] = mapped_column(String(8), default="自动")  # 自动/人工
    file_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 人工上传文件引用
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256 防篡改
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 上一条证据的 chain_hash（P4 哈希链）
    chain_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 链式哈希（P4 防篡改）
    operator_id: Mapped[int | None] = mapped_column(
        ForeignKey("sys_user.id"), nullable=True
    )  # 产生证据的操作人
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # 证据发生时间
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ComplianceCheck(Base):
    """合规核验（闭环追责）：核验状态机，不通过接问题整改闭环。"""

    __tablename__ = "compliance_check"

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("compliance_requirement.id"), index=True
    )
    check_type: Mapped[str] = mapped_column(String(16), default="巡查")  # 巡查/自查/攻防校验/复测
    status: Mapped[str] = mapped_column(String(16), default="未覆盖")  # 未覆盖/进行中/已核验/有缺口/已闭环
    result: Mapped[str | None] = mapped_column(String(8), nullable=True)  # 通过/不通过/部分
    issue_id: Mapped[int | None] = mapped_column(ForeignKey("issue.id"), nullable=True)  # 整改闭环收编点
    evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("compliance_evidence.id"), nullable=True
    )  # 支撑核验的关键证据
    assignee: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 核验责任人（逻辑引用 user）
    check_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DutyReport(Base):
    """履职报告（自证输出）：从证据链聚合，可导出/签署。"""

    __tablename__ = "duty_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), index=True)  # 冗余，行级隔离
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("contract.id"), nullable=True, index=True
    )  # 项目维度；null = 客户全局
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(8), default="草稿")  # 草稿/已生成/已签署
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # 聚合快照
    file_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 导出文件引用
    sign: Mapped[str] = mapped_column(String(16), default="未签署")  # 未签署/已签署
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ComplianceRequirementTemplate(Base):
    """监管要求模板库（全局，无客户归属）：等保2.0 / 密码测评 / 数据安全 / 公安部176号令 / 关基保护。"""

    __tablename__ = "compliance_requirement_template"

    id: Mapped[int] = mapped_column(primary_key=True)
    reg_source: Mapped[str] = mapped_column(String(32), index=True)  # 等保2.0/密码测评/数据安全/公安部176号令/关基保护
    domain: Mapped[str] = mapped_column(String(64))  # 标准领域，如 安全物理环境/数据分类分级
    title: Mapped[str] = mapped_column(String(128))  # 条款标题
    clause: Mapped[str] = mapped_column(Text)  # 要求原文
    category: Mapped[str] = mapped_column(String(16), default="技术")  # 技术/组织/制度/台账/流程
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True)
