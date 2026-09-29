from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Contract(Base):
    __tablename__ = "contract"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), index=True)
    type: Mapped[str] = mapped_column(String(32), default="安全服务")  # 安全服务/安全运维/设备升级/购买设备/机房改造/其他
    name: Mapped[str] = mapped_column(String(128))
    no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    has_onsite: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="洽谈中")  # 洽谈中/执行中/已到期/已续约
    # 合同原件导入抽取的补充字段（步骤 49）
    sign_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # 合同签署日期
    staff_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)  # 人员要求
    accept_standard: Mapped[str | None] = mapped_column(Text, nullable=True)  # 验收标准
    delivery_docs: Mapped[str | None] = mapped_column(Text, nullable=True)  # 交付文档
    acceptance_report_format: Mapped[str | None] = mapped_column(Text, nullable=True)  # 验收报告格式
    service_location: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 服务地点
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CmdbCi(Base):
    """服务对象 = CMDB 配置项"""

    __tablename__ = "cmdb_ci"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), index=True)  # 冗余，由合同派生，供行级隔离直接过滤
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract.id"), index=True)  # 服务对象归属合同
    name: Mapped[str] = mapped_column(String(128))  # 如 OA 系统 / XX 系统
    type: Mapped[str] = mapped_column(String(32), default="业务系统")  # 业务系统/网络设备/服务器/机房/数据库
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 脱敏
    status: Mapped[str] = mapped_column(String(16), default="在用")
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(16), default="在用")  # 新增/在用/变更/下线
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CmdbCiDependency(Base):
    """服务对象依赖关系：source 依赖 target（target 故障影响 source）。"""

    __tablename__ = "cmdb_ci_dependency"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_ci_id: Mapped[int] = mapped_column(ForeignKey("cmdb_ci.id"), index=True)
    target_ci_id: Mapped[int] = mapped_column(ForeignKey("cmdb_ci.id"), index=True)
    relation: Mapped[str] = mapped_column(String(32), default="依赖")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ContractItem(Base):
    __tablename__ = "contract_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract.id"), index=True)  # 冗余，由 ci.contract_id 派生，供 scope_filter/cycle 使用
    ci_id: Mapped[int | None] = mapped_column(ForeignKey("cmdb_ci.id"), nullable=True, index=True)  # 服务项目归属服务对象；null = 不针对具体系统（记作「//」）
    project: Mapped[str] = mapped_column(String(64))  # 运维项目枚举
    frequency: Mapped[int] = mapped_column(Integer, default=1)
    unit: Mapped[str] = mapped_column(String(16), default="月")  # 天/周/月/季度/半年/年/不定期
    sla_policy_id: Mapped[int | None] = mapped_column(
        ForeignKey("sla_policy.id"), nullable=True
    )
    accept_standard: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ContractArchive(Base):
    """合同原件档案：原件 Fernet 加密落盘，本表存元数据 + 提取字段 JSON。"""

    __tablename__ = "contract_archive"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("contract.id"), nullable=True, index=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id"), nullable=True, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(128))  # 加密文件名（upload/contracts/ 下）
    file_hash: Mapped[str] = mapped_column(String(64))  # SHA-256
    file_size: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(128))
    extracted: Mapped[str | None] = mapped_column(Text, nullable=True)  # 抽取字段 JSON
    status: Mapped[str] = mapped_column(String(16), default="待确认")  # 待确认/已确认
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("sys_user.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
