"""权限点 / 角色权限矩阵 单元测试。"""
import pytest
from fastapi import HTTPException

from app.api.v1.permissions import RolePermissionUpdate, update_role_permissions
from app.core.deps import permission_codes_of
from app.db.seed import PERMISSIONS, ROLE_PERMISSIONS
from app.models import SysAuditLog, SysPermission, SysRole, SysRolePermission, SysUser, SysUserRole


def _mk_role(db, code, name="角色", scope="platform"):
    role = SysRole(code=code, name=name, scope=scope)
    db.add(role)
    db.flush()
    return role


def _mk_user(db, username="u", name="用户"):
    user = SysUser(username=username, name=name, pwd_hash="x")
    db.add(user)
    db.flush()
    return user


def _mk_perm(db, code, ptype="menu"):
    perm = SysPermission(code=code, name=code, type=ptype)
    db.add(perm)
    db.flush()
    return perm


# ---- 权限点清单数据完整性 ----
def test_permission_catalog_no_duplicate_and_valid_refs():
    codes = [c for c, _, _ in PERMISSIONS]
    assert len(codes) == len(set(codes)), "权限点 code 不得重复"
    for role_code, perm_codes in ROLE_PERMISSIONS.items():
        assert all(c in codes for c in perm_codes), f"角色 {role_code} 引用了未定义的权限点"


# ---- permission_codes_of ----
def test_permission_codes_of_aggregates(db):
    role = _mk_role(db, "sys_ops")
    p1 = _mk_perm(db, "dashboard", "menu")
    p2 = _mk_perm(db, "user:write", "action")
    db.add(SysRolePermission(role_id=role.id, permission_id=p1.id))
    db.add(SysRolePermission(role_id=role.id, permission_id=p2.id))
    user = _mk_user(db, "u1")
    db.add(SysUserRole(user_id=user.id, role_id=role.id))
    db.flush()
    assert permission_codes_of(user, db) == {"dashboard", "user:write"}


def test_permission_codes_of_empty_without_role(db):
    user = _mk_user(db, "u2")
    assert permission_codes_of(user, db) == set()


# ---- 角色权限矩阵更新 ----
def test_update_role_permissions_rebuilds_and_audits(db):
    role = _mk_role(db, "ticket_mgr")
    p1 = _mk_perm(db, "work_order:write", "action")
    p2 = _mk_perm(db, "kb:write", "action")
    admin = _mk_user(db, "admin")
    db.add(SysRolePermission(role_id=role.id, permission_id=p1.id))
    db.flush()

    update_role_permissions("ticket_mgr", RolePermissionUpdate(permission_codes=["kb:write"]), user=admin, db=db)

    rows = db.query(SysRolePermission).filter(SysRolePermission.role_id == role.id).all()
    assert {r.permission_id for r in rows} == {p2.id}
    audit = db.query(SysAuditLog).filter(SysAuditLog.resource == "role_permission:ticket_mgr").all()
    assert len(audit) == 1


def test_update_role_permissions_unknown_role_404(db):
    admin = _mk_user(db, "admin")
    with pytest.raises(HTTPException) as e:
        update_role_permissions("no_such", RolePermissionUpdate(permission_codes=[]), user=admin, db=db)
    assert e.value.status_code == 404


def test_update_role_permissions_self_lock_guard(db):
    _mk_role(db, "sys_admin")
    admin = _mk_user(db, "admin")
    with pytest.raises(HTTPException) as e:
        update_role_permissions("sys_admin", RolePermissionUpdate(permission_codes=["dashboard"]), user=admin, db=db)
    assert e.value.status_code == 400


def test_update_role_permissions_unknown_permission_400(db):
    _mk_role(db, "ticket_mgr")
    admin = _mk_user(db, "admin")
    with pytest.raises(HTTPException) as e:
        update_role_permissions("ticket_mgr", RolePermissionUpdate(permission_codes=["nope:write"]), user=admin, db=db)
    assert e.value.status_code == 400


def test_update_role_permissions_dedupes_codes(db):
    role = _mk_role(db, "ticket_mgr")
    _mk_perm(db, "kb:write", "action")
    admin = _mk_user(db, "admin")

    update_role_permissions("ticket_mgr", RolePermissionUpdate(permission_codes=["kb:write", "kb:write"]), user=admin, db=db)

    rows = db.query(SysRolePermission).filter(SysRolePermission.role_id == role.id).all()
    assert len(rows) == 1
