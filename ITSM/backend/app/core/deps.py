"""依赖注入：数据库会话 / 当前用户 / 角色校验 / 客户行级隔离锚点。"""
from typing import Iterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session, aliased

from app.core.context import client_ip
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models import (
    Contract,
    ContractItem,
    Customer,
    Delivery,
    OrderReceive,
    SysRole,
    SysUser,
    SysUserRole,
    WorkOrder,
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _client_ip(request: Request) -> str | None:
    """取真实客户端 IP：优先 X-Real-IP，否则直连 client.host。

    只信任 X-Real-IP（nginx ``proxy_set_header X-Real-IP $remote_addr`` 会覆盖为真实
    对端地址，不可被客户端伪造）；不读 X-Forwarded-For——其首段可被客户端注入任意值。
    """
    if request is None:
        return None
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    request: Request = None,
) -> SysUser:
    """解析 Bearer Token 并加载当前用户；未登录/凭证无效/停用分别 401/401/403。

    同时捕获客户端 IP 到 ContextVar，供 audit_service.record 补全审计留痕。
    """
    client_ip.set(_client_ip(request))
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
    - WorkOrder / Delivery 经 contract 或 receive / work_order 链路过滤（左连接，
      避免 contract_id 为 NULL 时被内连接丢弃）；
    - 其余无 customer_id 的模型（如 ContractItem）经 `contract_id` 内连接过滤。
    平台侧用户（scope 为 None）不做过滤。
    """
    if scope is None:
        return q
    if model is Customer:
        return q.filter(model.id == scope)
    if hasattr(model, "customer_id"):
        return q.filter(model.customer_id == scope)
    if model is WorkOrder:
        q = q.outerjoin(Contract, model.contract_id == Contract.id)
        q = q.outerjoin(OrderReceive, model.receive_id == OrderReceive.id)
        item_contract = aliased(Contract)
        q = q.outerjoin(ContractItem, model.contract_item_id == ContractItem.id)
        q = q.outerjoin(item_contract, ContractItem.contract_id == item_contract.id)
        return q.filter(
            or_(
                Contract.customer_id == scope,
                OrderReceive.customer_id == scope,
                item_contract.customer_id == scope,
            )
        )
    if model is Delivery:
        wo_contract = aliased(Contract)
        item_contract = aliased(Contract)
        wo_item_contract = aliased(Contract)
        q = q.outerjoin(Contract, model.contract_id == Contract.id)
        q = q.outerjoin(WorkOrder, model.work_order_id == WorkOrder.id)
        q = q.outerjoin(wo_contract, WorkOrder.contract_id == wo_contract.id)
        q = q.outerjoin(OrderReceive, WorkOrder.receive_id == OrderReceive.id)
        q = q.outerjoin(ContractItem, model.contract_item_id == ContractItem.id)
        q = q.outerjoin(item_contract, ContractItem.contract_id == item_contract.id)
        wo_item = aliased(ContractItem)
        q = q.outerjoin(wo_item, WorkOrder.contract_item_id == wo_item.id)
        q = q.outerjoin(wo_item_contract, wo_item.contract_id == wo_item_contract.id)
        return q.filter(
            or_(
                Contract.customer_id == scope,
                wo_contract.customer_id == scope,
                OrderReceive.customer_id == scope,
                item_contract.customer_id == scope,
                wo_item_contract.customer_id == scope,
            )
        )
    return q.join(Contract, model.contract_id == Contract.id).filter(
        Contract.customer_id == scope
    )


def owning_customer_id(obj, db: Session) -> int | None:
    """解析对象归属的 customer_id；无归属返回 None。

    归属链路：直接 customer_id → contract_id → contract_item_id → receive_id → work_order_id。
    """
    if isinstance(obj, Customer):
        return obj.id
    cid = getattr(obj, "customer_id", None)
    if cid is not None:
        return cid
    cid = getattr(obj, "contract_id", None)
    if cid is not None:
        c = db.get(Contract, cid)
        if c is not None:
            return c.customer_id
    iid = getattr(obj, "contract_item_id", None)
    if iid is not None:
        item = db.get(ContractItem, iid)
        if item is not None:
            c = db.get(Contract, item.contract_id)
            if c is not None:
                return c.customer_id
    rid = getattr(obj, "receive_id", None)
    if rid is not None:
        r = db.get(OrderReceive, rid)
        if r is not None:
            return owning_customer_id(r, db)
    wid = getattr(obj, "work_order_id", None)
    if wid is not None:
        wo = db.get(WorkOrder, wid)
        if wo is not None:
            return owning_customer_id(wo, db)
    return None


def assert_scoped(obj, scope: int | None, db: Session) -> None:
    """行级隔离校验：客户侧用户访问非本客户资源时 404（防 IDOR）。"""
    if scope is not None and owning_customer_id(obj, db) != scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资源不存在或无权访问")
