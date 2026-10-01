"""权限管理：权限点清单 / 角色清单 / 角色权限矩阵读写。

- 读接口（权限点/角色/角色权限）按 `personnel` 菜单权限点控制（人员管理页可见者即可读）；
- 写接口（更新角色权限矩阵）按 `role:write` 权限点控制（默认仅 sys_admin）。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission
from app.models import SysPermission, SysRole, SysRolePermission, SysUser
from app.services.audit_service import record
from app.utils.response import ok

router = APIRouter(prefix="/permissions", tags=["权限管理"])

_ADMIN_ROLE = "sys_admin"
_SELF_LOCK_GUARD = "role:write"  # sys_admin 角色不可移除该权限点（防自锁）


class RolePermissionUpdate(BaseModel):
    permission_codes: list[str]


def _role_perm_codes(db: Session, role_id: int) -> list[str]:
    rows = (
        db.query(SysPermission.code)
        .join(SysRolePermission, SysRolePermission.permission_id == SysPermission.id)
        .filter(SysRolePermission.role_id == role_id)
        .all()
    )
    return [r[0] for r in rows]


@router.get("")
def list_permissions(user: SysUser = Depends(require_permission("personnel")), db: Session = Depends(get_db)):
    """权限点清单（含 type）。"""
    perms = db.query(SysPermission).order_by(SysPermission.id).all()
    return ok([{"code": p.code, "name": p.name, "type": p.type} for p in perms])


@router.get("/roles")
def list_roles(user: SysUser = Depends(require_permission("personnel")), db: Session = Depends(get_db)):
    """角色清单（code/name/scope）。"""
    roles = db.query(SysRole).order_by(SysRole.id).all()
    return ok([{"code": r.code, "name": r.name, "scope": r.scope} for r in roles])


@router.get("/roles/{code}/permissions")
def get_role_permissions(code: str, user: SysUser = Depends(require_permission("personnel")), db: Session = Depends(get_db)):
    """某角色当前权限点 codes。"""
    role = db.query(SysRole).filter(SysRole.code == code).first()
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "角色不存在")
    return ok(_role_perm_codes(db, role.id))


@router.put("/roles/{code}/permissions")
def update_role_permissions(
    code: str,
    body: RolePermissionUpdate,
    user: SysUser = Depends(require_permission("role:write")),
    db: Session = Depends(get_db),
):
    """全量更新角色权限矩阵（先删后插）。"""
    role = db.query(SysRole).filter(SysRole.code == code).first()
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "角色不存在")

    if role.code == _ADMIN_ROLE and _SELF_LOCK_GUARD not in body.permission_codes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "系统管理员角色不可移除「角色/权限矩阵配置」权限点")

    perm_ids: list[int] = []
    seen: set[str] = set()
    for pc in body.permission_codes:
        if pc in seen:
            continue
        seen.add(pc)
        p = db.query(SysPermission).filter(SysPermission.code == pc).first()
        if p is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"权限点不存在: {pc}")
        perm_ids.append(p.id)

    before = _role_perm_codes(db, role.id)
    db.query(SysRolePermission).filter(SysRolePermission.role_id == role.id).delete()
    for pid in perm_ids:
        db.add(SysRolePermission(role_id=role.id, permission_id=pid))

    record(
        db,
        user_id=user.id,
        action="update",
        resource=f"role_permission:{role.code}",
        before=str(before),
        after=str(body.permission_codes),
    )
    db.commit()
    return ok({"code": role.code, "permission_codes": body.permission_codes})
