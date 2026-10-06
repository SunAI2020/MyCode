"""数据看板：三行看板聚合（基本情况 / 执行情况 / 合规运营）。"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import customer_scope_of, get_db, require_role
from app.models import (
    ComplianceCheck,
    ComplianceEvidence,
    ComplianceRequirement,
    Contract,
    Customer,
    Delivery,
    Issue,
    KbArticle,
    OrderDispatch,
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
WORK_STATUS = ["待派单", "待执行", "执行中", "待验收", "待结单", "已结单", "已取消", "已关闭"]
ISSUE_STATUS = ["待整改", "整改中", "已关闭"]
LEVELS = ["严重", "高危", "中危", "低危", "信息"]
CATEGORIES = ["技术", "组织", "制度", "台账", "流程"]
CHECK_RESULTS = ["通过", "部分", "不通过"]
DISPATCH_WARN_STATUS = ["待派单", "待执行"]
ACCEPT_WARN_STATUS = ["执行中", "待验收", "待结单"]
FORECAST_STATUS = ["待执行", "执行中", "待验收", "待结单"]
SCHEDULE_START_WARN = ["待派单", "待执行"]
SCHEDULE_END_WARN = ["执行中", "待验收"]


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
    customers = {c.id: (c.short_name or c.name) for c in db.query(Customer).all()}
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
    customer_names = {c.id: (c.short_name or c.name) for c in db.query(Customer).all()}
    eff_customer = func.coalesce(WorkOrder.customer_id, Contract.customer_id)

    # 派单预警：客户 × (待派单/待执行) —— 已签约未派单 + 已派单未执行
    dw_rows = (
        db.query(eff_customer, WorkOrder.status, func.count(WorkOrder.id))
        .select_from(WorkOrder)
        .outerjoin(Contract, Contract.id == WorkOrder.contract_id)
        .filter(WorkOrder.status.in_(DISPATCH_WARN_STATUS))
        .group_by(eff_customer, WorkOrder.status)
        .all()
    )
    dw_map: dict = {}
    for cid, st, n in dw_rows:
        dw_map.setdefault(customer_names.get(cid, "未分配"), {})[st] = n
    dispatch_warning_by_customer = _stacked(dw_map, DISPATCH_WARN_STATUS)

    # 验收预警：客户 × (执行中/待验收/待结单) —— 未提交报告 + 未验收 + 未结单
    aw_rows = (
        db.query(eff_customer, WorkOrder.status, func.count(WorkOrder.id))
        .select_from(WorkOrder)
        .outerjoin(Contract, Contract.id == WorkOrder.contract_id)
        .filter(WorkOrder.status.in_(ACCEPT_WARN_STATUS))
        .group_by(eff_customer, WorkOrder.status)
        .all()
    )
    aw_map: dict = {}
    for cid, st, n in aw_rows:
        aw_map.setdefault(customer_names.get(cid, "未分配"), {})[st] = n
    acceptance_warning_by_customer = _stacked(aw_map, ACCEPT_WARN_STATUS)

    # 工期预警：客户 × (已过开始未执行/已过结束未验收/已延期)，工期日期取自当前派单 OrderDispatch
    today = date.today()
    sw_start_rows = (
        db.query(eff_customer, func.count(WorkOrder.id))
        .select_from(WorkOrder)
        .outerjoin(Contract, Contract.id == WorkOrder.contract_id)
        .join(OrderDispatch, OrderDispatch.id == WorkOrder.dispatch_id)
        .filter(WorkOrder.status.in_(SCHEDULE_START_WARN))
        .filter(OrderDispatch.service_start.isnot(None), OrderDispatch.service_start < today)
        .group_by(eff_customer)
        .all()
    )
    sw_end_rows = (
        db.query(eff_customer, func.count(WorkOrder.id))
        .select_from(WorkOrder)
        .outerjoin(Contract, Contract.id == WorkOrder.contract_id)
        .join(OrderDispatch, OrderDispatch.id == WorkOrder.dispatch_id)
        .filter(WorkOrder.status.in_(SCHEDULE_END_WARN))
        .filter(OrderDispatch.service_end.isnot(None), OrderDispatch.service_end < today)
        .group_by(eff_customer)
        .all()
    )
    sw_delay_rows = (
        db.query(eff_customer, func.count(WorkOrder.id))
        .select_from(WorkOrder)
        .outerjoin(Contract, Contract.id == WorkOrder.contract_id)
        .filter(WorkOrder.sla_deadline.isnot(None), func.date(WorkOrder.sla_deadline) < today)
        .filter(WorkOrder.status.notin_(["已结单", "已关闭", "已取消"]))
        .group_by(eff_customer)
        .all()
    )
    sw_map: dict = {}
    for cid, n in sw_start_rows:
        sw_map.setdefault(customer_names.get(cid, "未分配"), {})["已过开始未执行"] = n
    for cid, n in sw_end_rows:
        sw_map.setdefault(customer_names.get(cid, "未分配"), {})["已过结束未验收"] = n
    for cid, n in sw_delay_rows:
        sw_map.setdefault(customer_names.get(cid, "未分配"), {})["已延期"] = n
    schedule_warning_by_customer = _stacked(sw_map, ["已过开始未执行", "已过结束未验收", "已延期"])

    # 人员预计：人员 × (待执行/执行中/待验收/待结单)
    pf_rows = (
        db.query(SysUser.name, WorkOrder.status, func.count(WorkOrder.id))
        .select_from(WorkOrderAssignee)
        .join(WorkOrder, WorkOrder.id == WorkOrderAssignee.work_order_id)
        .join(SysUser, SysUser.id == WorkOrderAssignee.user_id)
        .filter(WorkOrderAssignee.is_active.is_(True))
        .filter(WorkOrder.status.in_(FORECAST_STATUS))
        .group_by(SysUser.name, WorkOrder.status)
        .all()
    )
    pf_map: dict = {}
    for name, st, n in pf_rows:
        pf_map.setdefault(name, {})[st] = n
    personnel_forecast = _stacked(pf_map, FORECAST_STATUS)

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

    customer_display = func.coalesce(func.nullif(Customer.short_name, ''), Customer.name)
    chk_rows = (
        db.query(customer_display, ComplianceCheck.result, func.count(ComplianceCheck.id))
        .select_from(ComplianceCheck)
        .join(ComplianceRequirement, ComplianceRequirement.id == ComplianceCheck.requirement_id)
        .join(Customer, Customer.id == ComplianceRequirement.customer_id)
        .filter(ComplianceCheck.result.isnot(None))
        .group_by(customer_display, ComplianceCheck.result)
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
            "dispatch_warning_by_customer": dispatch_warning_by_customer,
            "acceptance_warning_by_customer": acceptance_warning_by_customer,
            "schedule_warning_by_customer": schedule_warning_by_customer,
            "personnel_forecast": personnel_forecast,
            "issue_by_type_level": issue_by_type_level,
            "issue_by_type_status": issue_by_type_status,
            "compliance_by_reg_source": compliance_by_reg_source,
            "check_by_customer": check_by_customer,
            "coverage_by_customer": coverage_by_customer,
            "risk_by_customer": risk_by_customer,
        }
    )
