"""人员管理：系统用户（执行人/工程师）请求模型。"""
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    name: str
    password: str
    phone: str | None = None
    dept: str | None = None
    role_codes: list[str] = []  # 角色 code 列表，如 sys_ops / sec_staff
    customer_id: int | None = None  # 客户侧角色（cust_admin/cust_service）必填，作行级隔离锚点


class UserUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    dept: str | None = None
    status: str | None = None  # active / inactive
    password: str | None = None
    role_codes: list[str] | None = None
    customer_id: int | None = None
