"""合规运营指标与履职报告聚合（步骤 51 · P3）。

量化口径见文档 §七：覆盖率 / 闭环率 / 留痕完整率 / 风险敞口。
"""
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models import ComplianceCheck, ComplianceEvidence, ComplianceRequirement


def _enabled_ids(
    db: Session, *, customer_id: int | None = None, project_id: int | None = None
) -> list[int]:
    q = db.query(ComplianceRequirement).filter(ComplianceRequirement.status == "启用")
    if customer_id is not None:
        q = q.filter(ComplianceRequirement.customer_id == customer_id)
    if project_id is not None:
        q = q.filter(ComplianceRequirement.project_id == project_id)
    return [r.id for r in q.all()]


def compute_metrics(
    db: Session, *, customer_id: int | None = None, project_id: int | None = None
) -> dict:
    """合规量化指标。

    - coverage_rate（合规覆盖率）= 已关联履约证据的要求数 / 要求总数
    - closure_rate（闭环率）=（已核验 + 已闭环）要求数 / 要求总数
    - traceability_rate（留痕完整率）与覆盖率同口径（文档 §七 定义一致）
    - at_risk（风险敞口）= 未发起核验 或 核验状态 ∈ {未覆盖, 有缺口} 的要求数
    """
    ids = _enabled_ids(db, customer_id=customer_id, project_id=project_id)
    total = len(ids)

    def rate(x: int) -> float:
        return round(x / total, 4) if total else 0.0

    if total == 0:
        return {
            "total": 0, "covered": 0, "verified": 0, "at_risk": 0,
            "coverage_rate": 0.0, "closure_rate": 0.0, "traceability_rate": 0.0,
            "by_category": [],
        }

    covered = {
        r[0]
        for r in db.query(ComplianceEvidence.requirement_id)
        .filter(ComplianceEvidence.requirement_id.in_(ids))
        .distinct()
        .all()
    }
    check_rows = (
        db.query(ComplianceCheck.requirement_id, ComplianceCheck.status)
        .filter(ComplianceCheck.requirement_id.in_(ids))
        .all()
    )
    verified = {rid for rid, st in check_rows if st in ("已核验", "已闭环")}
    at_risk = {rid for rid, st in check_rows if st in ("未覆盖", "有缺口")}
    checked = {rid for rid, _ in check_rows}
    for rid in ids:
        if rid not in checked:
            at_risk.add(rid)  # 从未发起核验 = 未覆盖 = 风险敞口

    # 分维度（五大维度）覆盖统计，供看板分维展示
    req_map = {r.id: r for r in db.query(ComplianceRequirement).filter(ComplianceRequirement.id.in_(ids)).all()}
    by_category: dict[str, dict] = {}
    for rid in ids:
        r = req_map[rid]
        slot = by_category.setdefault(r.category, {"category": r.category, "total": 0, "covered": 0, "verified": 0})
        slot["total"] += 1
        if rid in covered:
            slot["covered"] += 1
        if rid in verified:
            slot["verified"] += 1

    return {
        "total": total,
        "covered": len(covered),
        "verified": len(verified),
        "at_risk": len(at_risk),
        "coverage_rate": rate(len(covered)),
        "closure_rate": rate(len(verified)),
        "traceability_rate": rate(len(covered)),
        "by_category": sorted(by_category.values(), key=lambda x: x["category"]),
    }


def build_report_snapshot(
    db: Session,
    *,
    customer_id: int,
    project_id: int | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict:
    """生成履职报告聚合快照：量化指标 + 覆盖矩阵 + 证据清单。"""
    metrics = compute_metrics(db, customer_id=customer_id, project_id=project_id)

    reqs = (
        db.query(ComplianceRequirement)
        .filter(
            ComplianceRequirement.status == "启用",
            ComplianceRequirement.customer_id == customer_id,
        )
        .order_by(ComplianceRequirement.category, ComplianceRequirement.id)
        .all()
    )
    if project_id is not None:
        reqs = [r for r in reqs if r.project_id == project_id]

    requirement_rows = []
    for r in reqs:
        ev_count = db.query(ComplianceEvidence).filter_by(requirement_id=r.id).count()
        latest = (
            db.query(ComplianceCheck)
            .filter_by(requirement_id=r.id)
            .order_by(ComplianceCheck.id.desc())
            .first()
        )
        requirement_rows.append(
            {
                "id": r.id,
                "clause": r.clause,
                "category": r.category,
                "source_type": r.source_type,
                "reg_source": r.reg_source,
                "evidence_count": ev_count,
                "check_status": latest.status if latest else "未覆盖",
            }
        )

    evidence_rows = [
        {
            "id": e.id,
            "requirement_id": e.requirement_id,
            "source_type": e.source_type,
            "source_id": e.source_id,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        }
        for e in db.query(ComplianceEvidence)
        .filter(ComplianceEvidence.requirement_id.in_([r["id"] for r in requirement_rows]))
        .order_by(ComplianceEvidence.id.desc())
        .all()
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": {
            "start": period_start.isoformat() if period_start else None,
            "end": period_end.isoformat() if period_end else None,
        },
        "metrics": metrics,
        "requirements": requirement_rows,
        "evidence": evidence_rows,
    }
