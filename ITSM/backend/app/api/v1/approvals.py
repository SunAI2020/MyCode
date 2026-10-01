"""审批流：申请 → 通过（自动流转）/ 拒绝，全程留痕。"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission, require_role
from app.models import Approval, ChangeOrder, Outsourcing, SysUser, WorkOrder
from app.schemas.approval import ApprovalCreate, ApprovalDecision, ApprovalOut
from app.services.audit_service import record
from app.services.evidence_service import collect_for_approval
from app.services.workflow_service import allowed_targets, assert_transition, log_transition
from app.utils.pagination import paginate
from app.utils.response import ok

router = APIRouter(prefix="/approvals", tags=["审批流"])

APPROVAL_ROLE = ("sys_admin", "ticket_mgr")

ENTITY_MODEL = {
    "work_order": WorkOrder,
    "change_order": ChangeOrder,
    "outsourcing": Outsourcing,
}


@router.post("")
def create_approval(
    body: ApprovalCreate,
    user: SysUser = Depends(require_role(*APPROVAL_ROLE)),
    db: Session = Depends(get_db),
):
    """发起审批申请：to_status 必须是当前状态的合法流转目标。"""
    model = ENTITY_MODEL.get(body.entity)
    if model is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不支持的审批对象")
    obj = db.get(model, body.entity_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "审批对象不存在")
    if body.to_status not in allowed_targets(db, body.entity, obj.status):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "非法流转目标")
    appr = Approval(
        entity=body.entity,
        entity_id=body.entity_id,
        from_status=obj.status,
        to_status=body.to_status,
        applicant_id=user.id,
        status="待审批",
        reason=body.reason,
    )
    db.add(appr)
    db.flush()
    record(db, user_id=user.id, action="apply_approval", resource=f"approval:{appr.id}", after=str(body.model_dump()))
    db.commit()
    return ok(ApprovalOut.model_validate(appr).model_dump())


@router.get("")
def list_approvals(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*APPROVAL_ROLE)),
    db: Session = Depends(get_db),
):
    q = db.query(Approval).order_by(Approval.id.desc())
    if status_filter is not None:
        q = q.filter(Approval.status == status_filter)
    return ok(paginate(q, page, size, ApprovalOut))


def _apply(db: Session, approval: Approval, to_status: str, operator_id: int) -> None:
    """审批通过后真正执行状态流转（二次校验 + 留痕）。"""
    model = ENTITY_MODEL[approval.entity]
    obj = db.get(model, approval.entity_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "审批对象不存在")
    assert_transition(db, approval.entity, obj.status, to_status)
    before = obj.status
    obj.status = to_status
    log_transition(
        db,
        entity=approval.entity,
        entity_id=approval.entity_id,
        from_status=before,
        to_status=to_status,
        operator_id=operator_id,
        note="审批通过自动流转",
    )


@router.post("/{aid}/approve")
def approve(
    aid: int,
    body: ApprovalDecision,
    user: SysUser = Depends(require_permission("approval:write")),
    db: Session = Depends(get_db),
):
    appr = db.get(Approval, aid)
    if appr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "审批不存在")
    if appr.applicant_id == user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "不能审批自己发起的申请")
    if appr.status != "待审批":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该审批已处理")
    try:
        _apply(db, appr, appr.to_status, user.id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    appr.status = "已通过"
    appr.approver_id = user.id
    appr.decision_note = body.note
    appr.decided_at = datetime.now(timezone.utc)
    # 合规证据自动采集：审批通过 → 按审批对象归集后匹配合规要求生成证据（步骤 51）
    collect_for_approval(db, appr, operator_id=user.id)
    record(db, user_id=user.id, action="approve", resource=f"approval:{aid}", after="已通过")
    db.commit()
    return ok(ApprovalOut.model_validate(appr).model_dump())


@router.post("/{aid}/reject")
def reject(
    aid: int,
    body: ApprovalDecision,
    user: SysUser = Depends(require_permission("approval:write")),
    db: Session = Depends(get_db),
):
    appr = db.get(Approval, aid)
    if appr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "审批不存在")
    if appr.applicant_id == user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "不能审批自己发起的申请")
    if appr.status != "待审批":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该审批已处理")
    appr.status = "已拒绝"
    appr.approver_id = user.id
    appr.decision_note = body.note
    appr.decided_at = datetime.now(timezone.utc)
    record(db, user_id=user.id, action="reject", resource=f"approval:{aid}", after="已拒绝")
    db.commit()
    return ok(ApprovalOut.model_validate(appr).model_dump())
