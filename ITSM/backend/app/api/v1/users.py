"""人员管理：系统用户（执行人/工程师名册）CRUD。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import customer_scope_of, get_db, require_role, role_rows_of
from app.core.security import hash_password
from app.models import Customer, OutsourceUser, Performance, SysRole, SysUser, SysUserRole, WorkOrderAssignee
from app.schemas.auth import RoleBrief, UserOut
from app.schemas.user import UserCreate, UserUpdate
from app.services.audit_service import record
from app.utils.response import ok

router = APIRouter(prefix="/users", tags=["人员管理"])

ROLE = ("sys_admin", "sys_ops", "ticket_mgr")
ADMIN = ("sys_admin", "sys_ops")


def _user_out(user: SysUser, roles: list[SysRole], customer_id: int | None = None) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        name=user.name,
        phone=user.phone,
        dept=user.dept,
        status=user.status,
        roles=[RoleBrief(code=r.code, name=r.name, scope=r.scope) for r in roles],
        customer_id=customer_id,
    )


def _resolve_roles(db: Session, role_codes: list[str]) -> list[SysRole]:
    """code -> SysRole；未知 code 报 400。"""
    roles: list[SysRole] = []
    for code in role_codes:
        role = db.query(SysRole).filter(SysRole.code == code).first()
        if role is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"角色不存在: {code}")
        roles.append(role)
    return roles


def _set_roles(db: Session, user_id: int, role_codes: list[str], customer_id: int | None = None) -> None:
    """重建用户角色（先删后插）；客户侧角色绑定 customer_id 作行级隔离锚点。"""
    db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete()
    for role in _resolve_roles(db, role_codes):
        cid = customer_id if role.scope == "customer" else None
        db.add(SysUserRole(user_id=user_id, role_id=role.id, customer_id=cid))


def _assert_customer_scope(db: Session, role_codes: list[str], customer_id: int | None) -> None:
    """客户侧角色（scope=customer）必须绑定具体客户，否则行级隔离失效（跨租户泄露）。"""
    roles = _resolve_roles(db, role_codes)
    if any(r.scope == "customer" for r in roles) and customer_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "客户侧角色（cust_admin/cust_service）必须指定所属客户")
    if customer_id is not None and db.get(Customer, customer_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "指定客户不存在")


def _assert_can_assign_roles(actor: SysUser, db: Session, role_codes: list[str]) -> None:
    """仅 sys_admin 可授予 sys_admin 角色（防越权提权）。"""
    if "sys_admin" not in role_codes:
        return
    actor_roles = {r.code for r in role_rows_of(actor, db)}
    if "sys_admin" not in actor_roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "仅系统管理员可授予系统管理员角色")


def _assert_can_manage_target(actor: SysUser, db: Session, target: SysUser) -> None:
    """目标用户含 sys_admin 角色时，仅 sys_admin 可管理（防越权接管/停用/删除超管）。"""
    target_roles = {r.code for r in role_rows_of(target, db)}
    if "sys_admin" not in target_roles:
        return
    actor_roles = {r.code for r in role_rows_of(actor, db)}
    if "sys_admin" not in actor_roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "仅系统管理员可管理系统管理员账号")


def _referencing_user(db: Session, uid: int) -> list[str]:
    """返回引用了该用户的业务数据标签（用于删除前的友好提示，避免 500）。"""
    labels: list[str] = []
    if db.query(WorkOrderAssignee.id).filter(WorkOrderAssignee.user_id == uid).first():
        labels.append("工单执行记录")
    if db.query(Performance.id).filter(Performance.user_id == uid).first():
        labels.append("绩效记录")
    if db.query(OutsourceUser.id).filter(OutsourceUser.user_id == uid).first():
        labels.append("外包名册")
    return labels


@router.get("")
def list_users(user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    """人员列表（执行人/工程师名册）。批量取角色，避免 N+1 查询。"""
    users = db.query(SysUser).order_by(SysUser.id).all()
    user_ids = [u.id for u in users]
    role_by_user: dict[int, list[SysRole]] = {}
    customer_by_user: dict[int, int] = {}
    if user_ids:
        role_rows = db.query(SysUserRole).filter(SysUserRole.user_id.in_(user_ids)).all()
        role_ids = {r.role_id for r in role_rows}
        role_map = {r.id: r for r in db.query(SysRole).filter(SysRole.id.in_(role_ids)).all()} if role_ids else {}
        for rr in role_rows:
            role = role_map.get(rr.role_id)
            if role is not None:
                role_by_user.setdefault(rr.user_id, []).append(role)
            if rr.customer_id is not None:
                customer_by_user[rr.user_id] = rr.customer_id
    return ok([_user_out(u, role_by_user.get(u.id, []), customer_by_user.get(u.id)).model_dump() for u in users])


@router.post("")
def create_user(body: UserCreate, user: SysUser = Depends(require_role(*ADMIN)), db: Session = Depends(get_db)):
    if db.query(SysUser).filter(SysUser.username == body.username).first() is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "用户名已存在")
    u = SysUser(
        username=body.username,
        name=body.name,
        phone=body.phone,
        dept=body.dept,
        pwd_hash=hash_password(body.password),
        status="active",
    )
    db.add(u)
    db.flush()
    _assert_can_assign_roles(user, db, body.role_codes)
    _assert_customer_scope(db, body.role_codes, body.customer_id)
    _set_roles(db, u.id, body.role_codes, body.customer_id)
    record(db, user_id=user.id, action="create", resource=f"user:{u.id}", after=str(body.model_dump(exclude={"password"})))
    db.commit()
    return ok(_user_out(u, role_rows_of(u, db), customer_scope_of(u, db)).model_dump())


@router.put("/{uid}")
def update_user(uid: int, body: UserUpdate, user: SysUser = Depends(require_role(*ADMIN)), db: Session = Depends(get_db)):
    u = db.get(SysUser, uid)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    _assert_can_manage_target(user, db, u)
    data = body.model_dump(exclude_unset=True)
    if "password" in data:
        if data["password"]:
            u.pwd_hash = hash_password(data.pop("password"))
        else:
            data.pop("password")
    role_codes = data.pop("role_codes", None)
    customer_id = data.pop("customer_id", None)
    for k, v in data.items():
        setattr(u, k, v)
    if role_codes is not None:
        _assert_can_assign_roles(user, db, role_codes)
        _assert_customer_scope(db, role_codes, customer_id)
        _set_roles(db, u.id, role_codes, customer_id)
    record(db, user_id=user.id, action="update", resource=f"user:{uid}", after=str(body.model_dump(exclude_unset=True, exclude={"password"})))
    db.commit()
    return ok(_user_out(u, role_rows_of(u, db), customer_scope_of(u, db)).model_dump())


@router.delete("/{uid}")
def delete_user(uid: int, user: SysUser = Depends(require_role(*ADMIN)), db: Session = Depends(get_db)):
    u = db.get(SysUser, uid)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    _assert_can_manage_target(user, db, u)
    if u.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能删除当前登录账号")
    refs = _referencing_user(db, uid)
    if refs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该人员存在关联业务数据，无法删除：" + "、".join(refs))
    db.query(SysUserRole).filter(SysUserRole.user_id == uid).delete()
    db.delete(u)
    record(db, user_id=user.id, action="delete", resource=f"user:{uid}")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该人员存在未解除的关联数据，无法删除")
    return ok({"deleted": uid})
