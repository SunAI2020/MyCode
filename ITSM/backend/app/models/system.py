from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysUser(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dept: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    pwd_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SysRole(Base):
    __tablename__ = "sys_role"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    scope: Mapped[str] = mapped_column(String(16), default="platform")  # platform / customer


class SysPermission(Base):
    __tablename__ = "sys_permission"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(16), default="menu")  # menu/button/api/field


class SysUserRole(Base):
    __tablename__ = "sys_user_role"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("sys_role.id"))
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id"), nullable=True
    )  # 客户侧行级隔离锚点


class SysRolePermission(Base):
    __tablename__ = "sys_role_permission"

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("sys_role.id"))
    permission_id: Mapped[int] = mapped_column(ForeignKey("sys_permission.id"))


class SysAuditLog(Base):
    __tablename__ = "sys_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str | None] = mapped_column(String(255), nullable=True)
    before: Mapped[str | None] = mapped_column(Text, nullable=True)
    after: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SysDict(Base):
    __tablename__ = "sys_dict"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
