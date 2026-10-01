"""工作流规则：CRUD + 有效流转查询。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission, require_role
from app.models import SysUser, WorkflowRule
from app.schemas.workflow import WorkflowRuleCreate, WorkflowRuleOut, WorkflowRuleUpdate
from app.services.audit_service import record
from app.services.workflow_service import DEFAULT_TRANSITIONS, allowed_targets
from app.utils.pagination import paginate
from app.utils.response import ok

READ_ROLE = ("sys_admin", "sys_ops", "ticket_mgr")

router = APIRouter(prefix="/workflow-rules", tags=["工作流"])


@router.get("/transitions")
def effective_transitions(
    user: SysUser = Depends(require_role(*READ_ROLE)),
    db: Session = Depends(get_db),
):
    """各实体有效流转 = 默认 ∪ DB（供前端流程配置界面渲染）。"""
    result = {}
    for entity, graph in DEFAULT_TRANSITIONS.items():
        merged = {}
        for from_status in graph:
            merged[from_status] = allowed_targets(db, entity, from_status)
        result[entity] = merged
    return ok(result)


@router.get("")
def list_rules(
    entity: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*READ_ROLE)),
    db: Session = Depends(get_db),
):
    q = db.query(WorkflowRule)
    if entity is not None:
        q = q.filter(WorkflowRule.entity == entity)
    return ok(paginate(q.order_by(WorkflowRule.id), page, size, WorkflowRuleOut))


@router.post("")
def create_rule(
    body: WorkflowRuleCreate,
    user: SysUser = Depends(require_permission("workflow:write")),
    db: Session = Depends(get_db),
):
    obj = WorkflowRule(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"workflow_rule:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(WorkflowRuleOut.model_validate(obj).model_dump())


@router.put("/{rid}")
def update_rule(
    rid: int,
    body: WorkflowRuleUpdate,
    user: SysUser = Depends(require_permission("workflow:write")),
    db: Session = Depends(get_db),
):
    obj = db.get(WorkflowRule, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工作流规则不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"workflow_rule:{rid}", after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(WorkflowRuleOut.model_validate(obj).model_dump())


@router.delete("/{rid}")
def delete_rule(rid: int, user: SysUser = Depends(require_permission("workflow:write")), db: Session = Depends(get_db)):
    obj = db.get(WorkflowRule, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工作流规则不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"workflow_rule:{rid}")
    db.commit()
    return ok({"deleted": rid})
