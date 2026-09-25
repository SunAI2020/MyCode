"""绩效考核：生成绩效 / 列表 / 聚合 / CRUD。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_role
from app.models import Performance, SysUser
from app.schemas.performance import PerformanceCreate, PerformanceOut, PerformanceUpdate
from app.services.audit_service import record
from app.services.performance_service import compute_perf_score, generate_performance, summarize
from app.utils.pagination import paginate
from app.utils.response import ok

ROLE = ("sys_admin", "sys_ops", "ticket_mgr")

router = APIRouter(tags=["绩效考核"])


@router.post("/work-orders/{wid}/performance/generate")
def generate(wid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    try:
        n = generate_performance(db, wid)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    record(db, user_id=user.id, action="generate_performance", resource=f"work_order:{wid}", after=f"generated={n}")
    db.commit()
    return ok({"generated": n})


@router.get("/performance")
def list_performance(
    user_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    q = db.query(Performance)
    if user_id is not None:
        q = q.filter(Performance.user_id == user_id)
    return ok(paginate(q, page, size, PerformanceOut))


@router.get("/performance/summary")
def performance_summary(
    user_id: int | None = Query(None),
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    return ok(summarize(db, user_id))


@router.post("/performance")
def create_performance(
    body: PerformanceCreate,
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    obj = Performance(**body.model_dump())
    obj.perf_score = compute_perf_score(
        body.workload, body.dispatch_price, body.ratio, body.quality_score, body.customer_score
    )
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"performance:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(PerformanceOut.model_validate(obj).model_dump())


@router.get("/performance/{pid}")
def get_performance(pid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    obj = db.get(Performance, pid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "绩效记录不存在")
    return ok(PerformanceOut.model_validate(obj).model_dump())


@router.put("/performance/{pid}")
def update_performance(
    pid: int,
    body: PerformanceUpdate,
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    obj = db.get(Performance, pid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "绩效记录不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.perf_score = compute_perf_score(obj.workload, obj.dispatch_price, obj.ratio, obj.quality_score, obj.customer_score)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"performance:{pid}", after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(PerformanceOut.model_validate(obj).model_dump())


@router.delete("/performance/{pid}")
def delete_performance(pid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    obj = db.get(Performance, pid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "绩效记录不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"performance:{pid}")
    db.commit()
    return ok({"deleted": pid})
