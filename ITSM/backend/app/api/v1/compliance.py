"""合规运营框架：合规要求 / 合规证据 / 合规核验 / 履职报告（步骤 51 · P1/P2/P3）。"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import (
    assert_scoped,
    customer_scope_of,
    get_current_user,
    get_db,
    require_role,
    scope_filter,
)
from app.models import (
    ComplianceCheck,
    ComplianceEvidence,
    ComplianceRequirement,
    Contract,
    ContractItem,
    Customer,
    DutyReport,
    Issue,
    SysUser,
    WorkOrder,
)
from app.schemas.compliance import (
    ComplianceCheckCreate,
    ComplianceCheckOut,
    ComplianceCheckUpdate,
    ComplianceEvidenceCreate,
    ComplianceEvidenceOut,
    ComplianceRequirementCreate,
    ComplianceRequirementOut,
    ComplianceRequirementUpdate,
    DutyReportCreate,
    DutyReportOut,
)
from app.services.audit_service import record
from app.services.compliance_service import build_report_snapshot, compute_metrics
from app.services.evidence_service import collect, verify_chain
from app.utils.pagination import paginate
from app.utils.response import ok
from app.utils.wo_no import next_work_order_no, work_order_no_scope

router = APIRouter(prefix="/compliance", tags=["合规运营"])

ROLE = ("sys_admin", "sys_ops", "ticket_mgr", "sec_staff")
ADMIN = ("sys_admin", "sys_ops")


def _validate_requirement_refs(
    db: Session, customer_id: int, project_id: int | None, source_type: str, source_id: int | None
) -> None:
    """校验合规要求的外键引用与客户归属一致（防跨租户 IDOR）。"""
    if project_id is not None:
        contract = db.get(Contract, project_id)
        if contract is None or contract.customer_id != customer_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "项目（合同）不存在或不属于该客户")
    if source_type == "服务项目" and source_id is not None:
        item = db.get(ContractItem, source_id)
        if item is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "服务项目不存在")
        contract = db.get(Contract, item.contract_id)
        if contract is None or contract.customer_id != customer_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "服务项目不属于该客户")


# ---- 合规要求 ----
@router.get("/requirements")
def list_requirements(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    customer_id: int | None = Query(None),
    project_id: int | None = Query(None),
    category: str | None = Query(None),
    source_type: str | None = Query(None),
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    q = db.query(ComplianceRequirement)
    if customer_id is not None:
        q = q.filter(ComplianceRequirement.customer_id == customer_id)
    if project_id is not None:
        q = q.filter(ComplianceRequirement.project_id == project_id)
    if category is not None:
        q = q.filter(ComplianceRequirement.category == category)
    if source_type is not None:
        q = q.filter(ComplianceRequirement.source_type == source_type)
    q = scope_filter(q, ComplianceRequirement, customer_scope_of(user, db))
    return ok(paginate(q.order_by(ComplianceRequirement.id.desc()), page, size, ComplianceRequirementOut))


@router.post("/requirements")
def create_requirement(
    body: ComplianceRequirementCreate,
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    if db.get(Customer, body.customer_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "客户不存在")
    scope = customer_scope_of(user, db)
    if scope is not None and body.customer_id != scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户创建合规要求")
    _validate_requirement_refs(db, body.customer_id, body.project_id, body.source_type, body.source_id)
    obj = ComplianceRequirement(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"compliance_requirement:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(ComplianceRequirementOut.model_validate(obj).model_dump())


@router.get("/requirements/{rid}")
def get_requirement(rid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    obj = db.get(ComplianceRequirement, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "合规要求不存在")
    assert_scoped(obj, customer_scope_of(user, db), db)
    return ok(ComplianceRequirementOut.model_validate(obj).model_dump())


@router.put("/requirements/{rid}")
def update_requirement(
    rid: int,
    body: ComplianceRequirementUpdate,
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    obj = db.get(ComplianceRequirement, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "合规要求不存在")
    assert_scoped(obj, customer_scope_of(user, db), db)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    _validate_requirement_refs(db, obj.customer_id, obj.project_id, obj.source_type, obj.source_id)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"compliance_requirement:{rid}", after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(ComplianceRequirementOut.model_validate(obj).model_dump())


@router.delete("/requirements/{rid}")
def delete_requirement(rid: int, user: SysUser = Depends(require_role(*ADMIN)), db: Session = Depends(get_db)):
    obj = db.get(ComplianceRequirement, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "合规要求不存在")
    assert_scoped(obj, customer_scope_of(user, db), db)
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"compliance_requirement:{rid}")
    db.commit()
    return ok({"deleted": rid})


# ---- 合规证据 ----
@router.post("/requirements/{rid}/evidence")
def add_evidence(
    rid: int,
    body: ComplianceEvidenceCreate,
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    req = db.get(ComplianceRequirement, rid)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "合规要求不存在")
    assert_scoped(req, customer_scope_of(user, db), db)
    if body.requirement_id != rid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "requirement_id 与路径不一致")
    ev = collect(
        db,
        requirement_id=rid,
        source_type=body.source_type,
        source_id=body.source_id,
        evidence_type=body.evidence_type,
        operator_id=user.id,
        content_hash=body.content_hash,
        note=body.note,
    )
    if body.file_ref:
        ev.file_ref = body.file_ref
    db.flush()
    record(db, user_id=user.id, action="add_evidence", resource=f"compliance_evidence:{ev.id}", after=str(body.model_dump()))
    db.commit()
    return ok(ComplianceEvidenceOut.model_validate(ev).model_dump())


@router.get("/requirements/{rid}/evidence")
def list_evidence(rid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    req = db.get(ComplianceRequirement, rid)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "合规要求不存在")
    assert_scoped(req, customer_scope_of(user, db), db)
    q = db.query(ComplianceEvidence).filter(ComplianceEvidence.requirement_id == rid).order_by(ComplianceEvidence.id.desc())
    return ok([ComplianceEvidenceOut.model_validate(e).model_dump() for e in q.all()])


@router.get("/requirements/{rid}/evidence/verify")
def verify_evidence_chain(rid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    """验证某合规要求下证据哈希链完整性（P4 防篡改）。"""
    req = db.get(ComplianceRequirement, rid)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "合规要求不存在")
    assert_scoped(req, customer_scope_of(user, db), db)
    return ok(verify_chain(db, rid))


# ---- 合规核验 ----
@router.post("/requirements/{rid}/checks")
def create_check(
    rid: int,
    body: ComplianceCheckCreate,
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    req = db.get(ComplianceRequirement, rid)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "合规要求不存在")
    assert_scoped(req, customer_scope_of(user, db), db)
    if body.requirement_id != rid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "requirement_id 与路径不一致")
    obj = ComplianceCheck(**body.model_dump(), status="进行中")
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"compliance_check:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(ComplianceCheckOut.model_validate(obj).model_dump())


@router.get("/checks")
def list_checks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    # ComplianceCheck 无 customer_id 冗余字段，join 合规要求后按归属做行级隔离
    q = db.query(ComplianceCheck).join(
        ComplianceRequirement, ComplianceCheck.requirement_id == ComplianceRequirement.id
    )
    q = scope_filter(q, ComplianceRequirement, customer_scope_of(user, db))
    if status is not None:
        q = q.filter(ComplianceCheck.status == status)
    return ok(paginate(q.order_by(ComplianceCheck.id.desc()), page, size, ComplianceCheckOut))


@router.put("/checks/{cid}")
def update_check(
    cid: int,
    body: ComplianceCheckUpdate,
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    obj = db.get(ComplianceCheck, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "核验不存在")
    req = db.get(ComplianceRequirement, obj.requirement_id)
    assert_scoped(req, customer_scope_of(user, db), db)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)

    # 证据归属校验：只能挂接同要求下的证据（防跨租户/跨要求）
    if body.evidence_id is not None:
        ev = db.get(ComplianceEvidence, body.evidence_id)
        if ev is None or ev.requirement_id != obj.requirement_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "证据不属于该合规要求")

    # 核验状态机：结果=通过 → 已核验；不通过/部分 → 有缺口 + 自动建整改问题（闭环收编）
    if body.result == "通过":
        obj.status = "已核验"
    elif body.result in ("不通过", "部分"):
        obj.status = "有缺口"
        if obj.issue_id is None:
            with work_order_no_scope(db):
                wo = WorkOrder(
                    no=next_work_order_no(db),
                    type="内部任务",
                    task_type="合规整改",
                    customer_id=req.customer_id,
                    contract_id=req.project_id,
                    description=f"合规核验缺口：{req.clause}",
                )
                db.add(wo)
                db.flush()
                issue = Issue(
                    work_order_id=wo.id,
                    requirement_id=req.id,
                    type="基线不合规",
                    level="高",
                    description=req.clause,
                )
                db.add(issue)
                db.flush()
                obj.issue_id = issue.id
                record(db, user_id=user.id, action="update", resource=f"compliance_check:{cid}", after=str(body.model_dump(exclude_unset=True)))
                db.commit()
            return ok(ComplianceCheckOut.model_validate(obj).model_dump())

    db.flush()
    record(db, user_id=user.id, action="update", resource=f"compliance_check:{cid}", after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(ComplianceCheckOut.model_validate(obj).model_dump())


# ---- 合规运营看板 ----
@router.get("/overview")
def overview(
    customer_id: int | None = Query(None),
    project_id: int | None = Query(None),
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    """合规指标：覆盖率 / 闭环率 / 留痕完整率 / 风险敞口（客户维度，无客户=平台全局）。"""
    scope = customer_scope_of(user, db)
    if scope is not None:
        if customer_id is not None and customer_id != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权查看其他客户")
        customer_id = scope
    return ok(compute_metrics(db, customer_id=customer_id, project_id=project_id))


# ---- 履职报告 ----
@router.post("/reports")
def create_report(
    body: DutyReportCreate,
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    """生成履职报告：聚合覆盖矩阵 + 证据清单 + 量化指标，快照存入 content_json。"""
    if db.get(Customer, body.customer_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "客户不存在")
    scope = customer_scope_of(user, db)
    if scope is not None and body.customer_id != scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户生成履职报告")
    snapshot = build_report_snapshot(
        db,
        customer_id=body.customer_id,
        project_id=body.project_id,
        period_start=body.period_start,
        period_end=body.period_end,
    )
    report = DutyReport(
        customer_id=body.customer_id,
        project_id=body.project_id,
        period_start=body.period_start,
        period_end=body.period_end,
        status="已生成",
        content_json=json.dumps(snapshot, ensure_ascii=False),
        created_by=user.id,
    )
    db.add(report)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"duty_report:{report.id}", after=str(body.model_dump()))
    db.commit()
    return ok(DutyReportOut.model_validate(report).model_dump())


@router.get("/reports")
def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    customer_id: int | None = Query(None),
    project_id: int | None = Query(None),
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    q = scope_filter(db.query(DutyReport), DutyReport, customer_scope_of(user, db))
    if customer_id is not None:
        q = q.filter(DutyReport.customer_id == customer_id)
    if project_id is not None:
        q = q.filter(DutyReport.project_id == project_id)
    return ok(paginate(q.order_by(DutyReport.id.desc()), page, size, DutyReportOut))


@router.get("/reports/{rid}")
def get_report(rid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    obj = db.get(DutyReport, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "履职报告不存在")
    assert_scoped(obj, customer_scope_of(user, db), db)
    data = DutyReportOut.model_validate(obj).model_dump()
    if obj.content_json:
        data["content"] = json.loads(obj.content_json)
    return ok(data)


@router.post("/reports/{rid}/sign")
def sign_report(rid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    obj = db.get(DutyReport, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "履职报告不存在")
    assert_scoped(obj, customer_scope_of(user, db), db)
    obj.status = "已签署"
    obj.sign = "已签署"
    db.flush()
    record(db, user_id=user.id, action="sign", resource=f"duty_report:{rid}")
    db.commit()
    return ok(DutyReportOut.model_validate(obj).model_dump())
