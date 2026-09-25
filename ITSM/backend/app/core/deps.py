"""依赖注入：数据库会话 / 当前用户 / 角色校验 / 客户行级隔离锚点。"""
from typing import Iterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models import Contract, Customer, SysRole, SysUser, SysUserRole

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> SysUser:
    """解析 Bearer Token 并加载当前用户；未登录/凭证无效/停用分别 401/401/403。"""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录或凭证缺失")
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "凭证无效或已过期")
    user = db.get(SysUser, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
    return user


def role_rows_of(user: SysUser, db: Session) -> list[SysRole]:
    """用户全部角色（SysRole 对象列表）。"""
    rows = db.query(SysUserRole).filter(SysUserRole.user_id == user.id).all()
    role_ids = [r.role_id for r in rows]
    if not role_ids:
        return []
    return db.query(SysRole).filter(SysRole.id.in_(role_ids)).all()


def customer_scope_of(user: SysUser, db: Session) -> int | None:
    """客户侧角色返回其绑定的 customer_id；平台侧角色返回 None（可看全部）。

    步骤四列表查询据此做行级隔离。
    """
    row = (
        db.query(SysUserRole)
        .filter(SysUserRole.user_id == user.id, SysUserRole.customer_id.isnot(None))
        .first()
    )
    return row.customer_id if row else None


def require_role(*allowed: str):
    """角色校验依赖：当前用户须持有 allowed 中至少一个角色，否则 403。"""

    def _dep(user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)) -> SysUser:
        roles = {r.code for r in role_rows_of(user, db)}
        if not roles & set(allowed):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "权限不足")
        return user

    return _dep


def scope_filter(q, model, scope: int | None):
    """行级隔离过滤：客户侧用户仅可见本客户数据。

    - model 含 `customer_id`：直接过滤；
    - 否则（contract_item / work_order）经 `contract` 关联过滤。
    平台侧用户（scope 为 None）不做过滤。
    """
    if scope is None:
        return q
    if model is Customer:
        return q.filter(model.id == scope)
    if hasattr(model, "customer_id"):
        return q.filter(model.customer_id == scope)
    return q.join(Contract, model.contract_id == Contract.id).filter(
        Contract.customer_id == scope
    )


def owning_customer_id(obj, db: Session) -> int | None:
    """解析对象归属的 customer_id；无归属返回 None。"""
    if isinstance(obj, Customer):
        return obj.id
    if getattr(obj, "customer_id", None) is not None:
        return obj.customer_id
    if getattr(obj, "contract_id", None) is not None:
        c = db.get(Contract, obj.contract_id)
        return c.customer_id if c else None
    return None


def assert_scoped(obj, scope: int | None, db: Session) -> None:
    """行级隔离校验：客户侧用户访问非本客户资源时 404（防 IDOR）。"""
    if scope is not None and owning_customer_id(obj, db) != scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资源不存在或无权访问")
