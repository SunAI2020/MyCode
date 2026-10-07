"""问题整改闭环：问题 / 整改 / 整改记录。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, aliased

from app.core.deps import customer_scope_of, get_current_user, get_db, require_permission, require_role
from app.models import CmdbCi, Contract, ContractItem, Customer, Issue, OrderReceive, Rectification, RectificationRecord, SysUser, WorkOrder, WorkOrderCi
from app.schemas.issue import (
    IssueCreate,
    IssueOut,
    IssueUpdate,
    RectificationCreate,
    RectificationOut,
    RectificationRecordOut,
    RectificationUpdate,
    RoundIn,
)
from app.services.audit_service import record
from app.services.issue_service import create_rectification, submit_round
from app.utils.pagination import paginate
from app.utils.response import ok

ROLE = ("sys_admin", "sys_ops", "ticket_mgr", "sec_staff")

router = APIRouter(tags=["问题整改"])


# ---- 问题 ----
@router.post("/work-orders/{wid}/issues")
def create_issue(
    wid: int,
    body: IssueCreate,
    user: SysUser = Depends(require_permission("issue:write")),
    db: Session = Depends(get_db),
):
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    obj = Issue(work_order_id=wid, **body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"issue:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(IssueOut.model_validate(obj).model_dump())


def _enrich_issues(db: Session, items: list[dict]) -> None:
    wids = {it["work_order_id"] for it in items if it.get("work_order_id")}
    if not wids:
        return
    wos = {w.id: w for w in db.query(WorkOrder).filter(WorkOrder.id.in_(wids)).all()}
    cids = {w.customer_id for w in wos.values() if w.customer_id}
    cname = {c.id: c.name for c in db.query(Customer).filter(Customer.id.in_(cids)).all()} if cids else {}
    ci_rows = (
        db.query(WorkOrderCi.work_order_id, CmdbCi.name)
        .join(CmdbCi, CmdbCi.id == WorkOrderCi.ci_id)
        .filter(WorkOrderCi.work_order_id.in_(wids))
        .all()
    )
    ci_map: dict[int, list[str]] = {}
    for wid, name in ci_rows:
        ci_map.setdefault(wid, []).append(name)
    for it in items:
        wo = wos.get(it["work_order_id"])
        if wo:
            it["work_order_no"] = wo.no
            it["customer_name"] = cname.get(wo.customer_id)
            names = ci_map.get(it["work_order_id"], [])
            if not names and wo.ci_id is not None:
                _ci = db.get(CmdbCi, wo.ci_id)
                if _ci:
                    names = [_ci.name]
            it["ci_names"] = "、".join(names)


@router.get("/issues")
def list_issues(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    type: str | None = Query(None),
    status: str | None = Query(None),
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    q = db.query(Issue)
    if type is not None:
        q = q.filter(Issue.type == type)
    if status is not None:
        q = q.filter(Issue.status == status)
    # 客户侧账号行级隔离：仅可见本客户工单下的问题（经 WorkOrder 链路反推客户）
    scope = customer_scope_of(user, db)
    if scope is not None:
        q = q.join(WorkOrder, Issue.work_order_id == WorkOrder.id)
        q = q.outerjoin(Contract, WorkOrder.contract_id == Contract.id)
        q = q.outerjoin(OrderReceive, WorkOrder.receive_id == OrderReceive.id)
        item_contract = aliased(Contract)
        q = q.outerjoin(ContractItem, WorkOrder.contract_item_id == ContractItem.id)
        q = q.outerjoin(item_contract, ContractItem.contract_id == item_contract.id)
        q = q.filter(or_(
            WorkOrder.customer_id == scope,
            Contract.customer_id == scope,
            OrderReceive.customer_id == scope,
            item_contract.customer_id == scope,
        ))
    data = paginate(q.order_by(Issue.id.desc()), page, size, IssueOut)
    _enrich_issues(db, data["items"])
    return ok(data)


@router.get("/issues/{iid}")
def get_issue(iid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    obj = db.get(Issue, iid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "问题不存在")
    return ok(IssueOut.model_validate(obj).model_dump())


@router.put("/issues/{iid}")
def update_issue(
    iid: int,
    body: IssueUpdate,
    user: SysUser = Depends(require_permission("issue:write")),
    db: Session = Depends(get_db),
):
    obj = db.get(Issue, iid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "问题不存在")
    before = {k: getattr(obj, k) for k in body.model_dump(exclude_unset=True)}
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"issue:{iid}", before=str(before), after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(IssueOut.model_validate(obj).model_dump())


@router.delete("/issues/{iid}")
def delete_issue(iid: int, user: SysUser = Depends(require_permission("issue:delete")), db: Session = Depends(get_db)):
    obj = db.get(Issue, iid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "问题不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"issue:{iid}")
    db.commit()
    return ok({"deleted": iid})


# ---- 整改 ----
@router.post("/issues/{iid}/rectifications")
def create_rect(
    iid: int,
    body: RectificationCreate,
    user: SysUser = Depends(require_permission("issue:write")),
    db: Session = Depends(get_db),
):
    try:
        obj = create_rectification(db, iid, body.plan, body.deadline, body.assignee)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    record(db, user_id=user.id, action="create", resource=f"rectification:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(RectificationOut.model_validate(obj).model_dump())


@router.get("/rectifications")
def list_rects(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    return ok(paginate(db.query(Rectification), page, size, RectificationOut))


@router.get("/rectifications/{rid}")
def get_rect(rid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    obj = db.get(Rectification, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "整改不存在")
    return ok(RectificationOut.model_validate(obj).model_dump())


@router.put("/rectifications/{rid}")
def update_rect(
    rid: int,
    body: RectificationUpdate,
    user: SysUser = Depends(require_permission("issue:write")),
    db: Session = Depends(get_db),
):
    obj = db.get(Rectification, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "整改不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"rectification:{rid}", after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(RectificationOut.model_validate(obj).model_dump())


@router.post("/rectifications/{rid}/rounds")
def submit_round_endpoint(
    rid: int,
    body: RoundIn,
    user: SysUser = Depends(require_permission("issue:write")),
    db: Session = Depends(get_db),
):
    if body.effect not in ("通过", "不通过", "部分完成"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "effect 须为 通过/不通过/部分完成")
    try:
        rec = submit_round(db, rid, body.action, body.executor, body.effect)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    record(db, user_id=user.id, action="submit_round", resource=f"rectification:{rid}", after=str(body.model_dump()))
    db.commit()
    return ok(RectificationRecordOut.model_validate(rec).model_dump())


@router.get("/rectifications/{rid}/records")
def list_records(rid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    q = db.query(RectificationRecord).filter(RectificationRecord.rectification_id == rid)
    return ok([RectificationRecordOut.model_validate(r).model_dump() for r in q.all()])
