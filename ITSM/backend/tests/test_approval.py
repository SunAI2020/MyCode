"""审批流单测：申请 → 通过（自动流转）/ 拒绝（不流转）/ 非法目标拒绝。"""
import pytest
from fastapi import HTTPException

from app.api.v1.approvals import approve, create_approval, reject
from app.models import ChangeOrder, SysRole, SysUser, SysUserRole
from app.schemas.approval import ApprovalCreate, ApprovalDecision


def _mk_user(db, username):
    role = db.query(SysRole).filter_by(code="ticket_mgr").first()
    if role is None:
        role = SysRole(code="ticket_mgr", name="工单管理", scope="platform")
        db.add(role)
        db.flush()
    u = SysUser(username=username, name=username, pwd_hash="x")
    db.add(u)
    db.flush()
    db.add(SysUserRole(user_id=u.id, role_id=role.id))
    db.commit()
    return u


def test_apply_approve_transitions(db):
    applicant = _mk_user(db, "mgr1")
    approver = _mk_user(db, "mgr2")
    co = ChangeOrder(ci_id=1, status="待审批")
    db.add(co)
    db.commit()

    data = create_approval(
        ApprovalCreate(entity="change_order", entity_id=co.id, to_status="已批准"), user=applicant, db=db
    )["data"]
    aid = data["id"]

    data2 = approve(aid, ApprovalDecision(note="同意"), user=approver, db=db)["data"]
    assert data2["status"] == "已通过"
    assert db.get(ChangeOrder, co.id).status == "已批准"  # 审批通过真正流转


def test_reject_does_not_transition(db):
    applicant = _mk_user(db, "mgr1")
    approver = _mk_user(db, "mgr2")
    co = ChangeOrder(ci_id=1, status="待审批")
    db.add(co)
    db.commit()

    data = create_approval(
        ApprovalCreate(entity="change_order", entity_id=co.id, to_status="已批准"), user=applicant, db=db
    )["data"]
    reject(data["id"], ApprovalDecision(note="驳回"), user=approver, db=db)
    assert db.get(ChangeOrder, co.id).status == "待审批"  # 拒绝不流转


def test_invalid_target_rejected(db):
    u = _mk_user(db, "mgr")
    co = ChangeOrder(ci_id=1, status="草稿")
    db.add(co)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        create_approval(
            ApprovalCreate(entity="change_order", entity_id=co.id, to_status="已批准"), user=u, db=db
        )
    assert exc.value.status_code == 400  # 草稿 不能直接到 已批准


def test_self_approval_rejected(db):
    u = _mk_user(db, "mgr")
    co = ChangeOrder(ci_id=1, status="待审批")
    db.add(co)
    db.commit()

    data = create_approval(
        ApprovalCreate(entity="change_order", entity_id=co.id, to_status="已批准"), user=u, db=db
    )["data"]
    # 申请人不能审批自己的申请（职责分离）
    with pytest.raises(HTTPException) as exc:
        approve(data["id"], ApprovalDecision(note="同意"), user=u, db=db)
    assert exc.value.status_code == 403
