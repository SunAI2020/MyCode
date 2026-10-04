"""数据看板：三行看板聚合（基本情况 / 执行情况 / 合规运营）。"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import customer_scope_of, get_db, require_role
from app.models import (
    ComplianceCheck,
    ComplianceEvidence,
    ComplianceRequirement,
    Contract,
    ContractItem,
    Customer,
    Delivery,
    Issue,
    KbArticle,
    Outsourcing,
    Performance,
    SysUser,
    WorkOrder,
    WorkOrderAssignee,
)
from app.services.compliance_service import compute_metrics
from app.utils.response import ok

router = APIRouter(prefix="/dashboard", tags=["数据看板"])

ROLE = ("sys_admin", "sys_ops", "ticket_mgr")

# 叠加维度固定顺序，保证 series 稳定、无数据补 0
WORK_STATUS = ["待派单", "待执行", "执行中", "待验收", "已验收", "已结单", "已取消", "已关闭"]
ISSUE_STATUS = ["待整改", "整改中", "已关闭"]
LEVELS = ["严重", "高危", "中危", "低危", "信息"]
CATEGORIES = ["技术", "组织", "制度", "台账", "流程"]
CHECK_RESULTS = ["通过", "部分", "不通过"]


def _pie(rows) -> list[dict]:
    """聚合行 → 饼图数据 [{name, value}]。"""
    return [{"name": name or "未分类", "value": int(v)} for name, v in rows]


def _stacked(data_map: dict, series_order: list[str], top: int = 10) -> dict:
    """{category: {series_name: value}} → {categories, series}，按总数降序取 Top N。

    只保留图中实际出现过的叠加维度（series），未出现的状态不在图例中标出。
    """
    scored = sorted(data_map.items(), key=lambda kv: -sum(kv[1].values()))
    categories = [c for c, _ in scored[:top]]
    present = {sname for m in data_map.values() for sname in m}
    series = [
        {"name": sname, "data": [data_map.get(c, {}).get(sname, 0) for c in categories]}
        for sname in series_order if sname in present
    ]
    return {"categories": categories, "series": series}


def _compliance_by_customer(db: Session) -> dict:
    """按 customer × category 聚合合规要求总数 / 已覆盖 / 风险敞口。

    风险敞口以「最新一次核验状态」为准（避免历史「有缺口」行高估）；
    从未核验或最新状态 ∈ {未覆盖, 进行中, 有缺口} 均计为风险。
    """
    reqs = db.query(ComplianceRequirement).filter(ComplianceRequirement.status == "启用").all()
    req_ids = [r.id for r in reqs]
    covered: set[int] = set()
    latest: dict[int, str] = {}
    if req_ids:
        covered = {
            r[0]
            for r in db.query(ComplianceEvidence.requirement_id)
            .filter(ComplianceEvidence.requirement_id.in_(req_ids))
            .distinct()
            .all()
        }
        for rid, st in (
            db.query(ComplianceCheck.requirement_id, ComplianceCheck.status)
            .filter(ComplianceCheck.requirement_id.in_(req_ids))
            .order_by(ComplianceCheck.id)
            .all()
        ):
            latest[rid] = st  # 升序遍历，最后写入即最新一次核验状态

    risk_status = {"未覆盖", "进行中", "有缺口"}
    customers = {c.id: c.name for c in db.query(Customer).all()}
    agg: dict = {}
    for r in reqs:
        cname = customers.get(r.customer_id, "未分配")
        cat = r.category if r.category in CATEGORIES else "其他"
        slot = agg.setdefault(cname, {}).setdefault(cat, {"total": 0, "covered": 0, "at_risk": 0})
        slot["total"] += 1
        if r.id in covered:
            slot["covered"] += 1
        st = latest.get(r.id)
        if st is None or st in risk_status:
            slot["at_risk"] += 1
    return agg


@router.get("")
def dashboard(user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    """三行看板：基本情况 / 执行情况 / 合规运营。"""
    # 全局管理看板：拒绝带客户 scope 的用户，防止向客户侧泄露跨租户聚合数据
    if customer_scope_of(user, db) is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权查看全局看板")

    # ---- 第一行：基本情况 ----
    customers_by_industry = _pie(db.query(Customer.industry, func.count(Customer.id)).group_by(Customer.industry).all())
    contracts_by_status = _pie(db.query(Contract.status, func.count(Contract.id)).group_by(Contract.status).all())
    work_orders_by_status = _pie(db.query(WorkOrder.status, func.count(WorkOrder.id)).group_by(WorkOrder.status).all())

    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    eng_rows = (
        db.query(SysUser.name, WorkOrder.status, func.count(WorkOrder.id))
        .select_from(WorkOrderAssignee)
        .join(WorkOrder, WorkOrder.id == WorkOrderAssignee.work_order_id)
        .join(SysUser, SysUser.id == WorkOrderAssignee.user_id)
        .filter(WorkOrder.created_at >= one_year_ago)
        .group_by(SysUser.name, WorkOrder.status)
        .all()
    )
    eng_map: dict = {}
    for name, st, n in eng_rows:
        eng_map.setdefault(name, {})[st] = n
    engineer_workload = _stacked(eng_map, WORK_STATUS)

    # ---- 第二行：执行情况 ----
    # 服务类别以 contract_item.project 实时为准（改名即时生效），无关联工单退回快照 project
    proj_label = func.coalesce(ContractItem.project, WorkOrder.project)
    proj_rows = (
        db.query(proj_label, WorkOrder.status, func.count(WorkOrder.id))
        .outerjoin(ContractItem, WorkOrder.contract_item_id == ContractItem.id)
        .filter(proj_label.isnot(None))
        .group_by(proj_label, WorkOrder.status)
        .all()
    )
    proj_map: dict = {}
    for proj, st, n in proj_rows:
        proj_map.setdefault(proj, {})[st] = n
    project_workload = _stacked(proj_map, WORK_STATUS)

    il_rows = db.query(Issue.type, Issue.level, func.count(Issue.id)).group_by(Issue.type, Issue.level).all()
    il_map: dict = {}
    for it, lv, n in il_rows:
        il_map.setdefault(it, {})[lv] = n
    issue_by_type_level = _stacked(il_map, LEVELS)

    ist_rows = db.query(Issue.type, Issue.status, func.count(Issue.id)).group_by(Issue.type, Issue.status).all()
    ist_map: dict = {}
    for it, st, n in ist_rows:
        ist_map.setdefault(it, {})[st] = n
    issue_by_type_status = _stacked(ist_map, ISSUE_STATUS)

    perf_rows = (
        db.query(SysUser.name, func.sum(Performance.perf_score), func.avg(Performance.customer_score))
        .select_from(Performance)
        .join(SysUser, SysUser.id == Performance.user_id)
        .group_by(SysUser.name)
        .all()
    )
    perf_map: dict = {}
    for name, total, cust in perf_rows:
        perf_map[name] = {"绩效总分": float(total or 0), "客户评价": round(float(cust or 0), 2)}
    performance_by_engineer = _stacked(perf_map, ["绩效总分", "客户评价"])

    # ---- 第三行：合规运营 ----
    reg_rows = (
        db.query(ComplianceRequirement.reg_source, ComplianceRequirement.category, func.count(ComplianceRequirement.id))
        .filter(ComplianceRequirement.reg_source.isnot(None))
        .group_by(ComplianceRequirement.reg_source, ComplianceRequirement.category)
        .all()
    )
    reg_map: dict = {}
    for src, cat, n in reg_rows:
        reg_map.setdefault(src, {})[cat] = n
    compliance_by_reg_source = _stacked(reg_map, CATEGORIES)

    chk_rows = (
        db.query(Customer.name, ComplianceCheck.result, func.count(ComplianceCheck.id))
        .select_from(ComplianceCheck)
        .join(ComplianceRequirement, ComplianceRequirement.id == ComplianceCheck.requirement_id)
        .join(Customer, Customer.id == ComplianceRequirement.customer_id)
        .filter(ComplianceCheck.result.isnot(None))
        .group_by(Customer.name, ComplianceCheck.result)
        .all()
    )
    chk_map: dict = {}
    for cname, res, n in chk_rows:
        chk_map.setdefault(cname, {})[res] = n
    check_by_customer = _stacked(chk_map, CHECK_RESULTS)

    cust_agg = _compliance_by_customer(db)
    cov_map: dict = {}
    risk_map: dict = {}
    for cname, cats in cust_agg.items():
        for cat, slot in cats.items():
            cov_map.setdefault(cname, {})[cat] = round(slot["covered"] / slot["total"] * 100, 1) if slot["total"] else 0
            risk_map.setdefault(cname, {})[cat] = slot["at_risk"]
    coverage_by_customer = _stacked(cov_map, CATEGORIES)
    risk_by_customer = _stacked(risk_map, CATEGORIES)

    perf_top = (
        db.query(Performance.user_id, SysUser.name, func.sum(Performance.perf_score))
        .join(SysUser, Performance.user_id == SysUser.id)
        .group_by(Performance.user_id, SysUser.name)
        .order_by(func.sum(Performance.perf_score).desc())
        .limit(5)
        .all()
    )

    return ok(
        {
            "customers": db.query(func.count(Customer.id)).scalar() or 0,
            "contracts": {
                "total": db.query(func.count(Contract.id)).scalar() or 0,
                "by_status": dict(db.query(Contract.status, func.count(Contract.id)).group_by(Contract.status).all()),
            },
            "work_orders": {
                "total": db.query(func.count(WorkOrder.id)).scalar() or 0,
                "by_status": dict(db.query(WorkOrder.status, func.count(WorkOrder.id)).group_by(WorkOrder.status).all()),
            },
            "deliveries": {
                "total": db.query(func.count(Delivery.id)).scalar() or 0,
                "signed": db.query(func.count(Delivery.id)).filter(Delivery.sign == "已签署").scalar() or 0,
            },
            "kb_articles": db.query(func.count(KbArticle.id)).scalar() or 0,
            "outsourcing": {
                "total": db.query(func.count(Outsourcing.id)).scalar() or 0,
                "total_price": float(db.query(func.coalesce(func.sum(Outsourcing.price), 0)).scalar() or 0),
            },
            "performance_top": [
                {"user_id": uid, "name": name, "total_score": float(s)}
                for uid, name, s in perf_top
            ],
            "compliance": compute_metrics(db),
            "issues": {
                "total": db.query(func.count(Issue.id)).scalar() or 0,
                "by_status": dict(db.query(Issue.status, func.count(Issue.id)).group_by(Issue.status).all()),
                "by_type": dict(db.query(Issue.type, func.count(Issue.id)).group_by(Issue.type).all()),
                "by_level": dict(db.query(Issue.level, func.count(Issue.id)).group_by(Issue.level).all()),
            },
            # 三行看板图表
            "customers_by_industry": customers_by_industry,
            "contracts_by_status": contracts_by_status,
            "work_orders_by_status": work_orders_by_status,
            "engineer_workload": engineer_workload,
            "project_workload": project_workload,
            "issue_by_type_level": issue_by_type_level,
            "issue_by_type_status": issue_by_type_status,
            "performance_by_engineer": performance_by_engineer,
            "compliance_by_reg_source": compliance_by_reg_source,
            "check_by_customer": check_by_customer,
            "coverage_by_customer": coverage_by_customer,
            "risk_by_customer": risk_by_customer,
        }
    )
