"""认证相关请求/响应模型。"""
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RoleBrief(BaseModel):
    code: str
    name: str
    scope: str


class UserOut(BaseModel):
    id: int
    username: str
    name: str
    phone: str | None = None
    dept: str | None = None
    status: str = "active"
    roles: list[RoleBrief] = []
    permissions: list[str] = []  # 经角色聚合的权限点 code（menu/action），前端据此裁剪菜单与按钮
    customer_id: int | None = None  # 客户侧行级隔离锚点（平台侧为 None）


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
