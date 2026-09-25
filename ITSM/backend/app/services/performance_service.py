"""绩效考核业务逻辑：加权公式 + 换岗分摊 + 聚合。"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ContractItem, OrderDispatch, Performance, WorkOrder, WorkOrderAssignee


def compute_perf_score(
    workload: float, dispatch_price: float, ratio: float,
    quality_score: float, customer_score: float,
) -> float:
    """perf_score = workload × dispatch_price × (ratio/100) × quality × customer"""
    return round(
        float(workload) * float(dispatch_price) * (float(ratio) / 100.0)
        * float(quality_score) * float(customer_score),
        2,
    )


def _resolve_dispatch_price(db: Session, wo: WorkOrder) -> float:
    disp = db.query(OrderDispatch).filter_by(work_order_id=wo.id).first()
    if disp is not None and disp.dispatch_price is not None:
        return float(disp.dispatch_price)
    if wo.contract_item_id is not None:
        item = db.get(ContractItem, wo.contract_item_id)
        if item is not None and item.price is not None:
            return float(item.price)
    return 0.0


def generate_performance(db: Session, work_order_id: int) -> int:
    """从工单执行人（含已离岗）生成绩效，换岗按各人实际承担比例精确归属。幂等（删除重建）。"""
    wo = db.get(WorkOrder, work_order_id)
    if wo is None:
        raise ValueError("工单不存在")
    assignees = db.query(WorkOrderAssignee).filter_by(work_order_id=work_order_id).all()
    if not assignees:
        raise ValueError("工单无执行人")
    db.query(Performance).filter_by(work_order_id=work_order_id).delete()
    price = _resolve_dispatch_price(db, wo)
    for a in assignees:
        workload = float(a.actual_hours) if a.actual_hours is not None else 0.0
        ratio = float(a.workload_ratio)
        perf = Performance(
            user_id=a.user_id,
            work_order_id=work_order_id,
            contract_item_id=wo.contract_item_id,
            workload=workload,
            dispatch_price=price,
            ratio=ratio,
            quality_score=1.0,
            customer_score=1.0,
        )
        perf.perf_score = compute_perf_score(workload, price, ratio, 1.0, 1.0)
        db.add(perf)
    db.commit()
    return len(assignees)


def summarize(db: Session, user_id: int | None = None) -> list[dict]:
    """按人聚合：总绩效分 + 条数。"""
    q = db.query(
        Performance.user_id,
        func.sum(Performance.perf_score).label("total_score"),
        func.count(Performance.id).label("cnt"),
    )
    if user_id is not None:
        q = q.filter(Performance.user_id == user_id)
    q = q.group_by(Performance.user_id)
    return [{"user_id": uid, "total_score": float(t), "count": int(c)} for uid, t, c in q.all()]
