"""报告台账模型。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Report(Base):
    __tablename__ = "report"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    report_type: Mapped[str] = mapped_column(String(32), default="运维报告")  # 运维报告/履职报告/验收报告/安全报告/其他
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customer.id"), nullable=True, index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contract.id"), nullable=True, index=True)
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_order.id"), nullable=True, index=True)
    report_no: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 报告编号
    status: Mapped[str] = mapped_column(String(16), default="草稿")  # 草稿/已提交/已签署
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 报告文件（服务报告附件）：加密入库 + 脱敏文本预览
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 原始文件名
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 由扩展名派生，不信任客户端
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 原始字节数
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256
    content_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # Fernet 加密后的文件内容
    masked_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # 脱敏后的文本（预览/搜索）
    report_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # 结构化报告内容（工作内容/安全问题统计/详情）JSON 文本
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
