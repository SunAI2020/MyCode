"""技能矩阵模型：人员 × 服务类别 × 等级（支撑智能派单）。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EngineerSkill(Base):
    __tablename__ = "engineer_skill"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), index=True)
    skill: Mapped[str] = mapped_column(String(64))  # 服务类别：漏洞扫描/渗透测试/…
    level: Mapped[str] = mapped_column(String(8), default="中级")  # 初级/中级/高级
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
