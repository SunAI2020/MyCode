"""数据看板：多维聚合统计（合同/工单/交付/知识/外包/绩效）。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import customer_scope_of, get_db, require_role
from app.models import (
    Contract,
    Customer,
    Delivery,
    KbArticle,
    Outsourcing,
    Performance,
    SysUser,
    WorkOrder,
)
from app.services.compliance_service import compute_metrics
from app.utils.response import ok

router = APIRouter(prefix="/dashboard", tags=["数据看板"])

ROLE = ("sys_admin", "sys_ops", "ticket_mgr")


@router.get("")
def dashboard(user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    """多维统计：客户/合同/工单/交付/知识/外包/绩效 Top5。"""
    # 全局管理看板：拒绝带客户 scope 的用户，防止向客户侧泄露跨租户聚合数据
    if customer_scope_of(user, db) is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权查看全局看板")
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
        }
    )
