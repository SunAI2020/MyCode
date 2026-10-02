"""客户 CRUD。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import (
    assert_scoped,
    customer_scope_of,
    get_current_user,
    get_db,
    require_permission,
    scope_filter,
)
from app.models import Contract, Customer, SysUser
from app.core.security import mask_sensitive, masked_page
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerUpdate
from app.services.audit_service import record
from app.utils.pagination import paginate
from app.utils.response import ok

router = APIRouter(prefix="/customers", tags=["客户"])


@router.get("")
def list_customers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    q = scope_filter(db.query(Customer), Customer, scope)
    return ok(masked_page(paginate(q, page, size, CustomerOut), scope))


@router.post("")
def create_customer(
    body: CustomerCreate,
    user: SysUser = Depends(require_permission("customer:write")),
    db: Session = Depends(get_db),
):
    if db.query(Customer).filter(Customer.name == body.name).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "客户名称已存在")
    obj = Customer(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"customer:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(CustomerOut.model_validate(obj).model_dump())


@router.get("/{cid}")
def get_customer(
    cid: int,
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    obj = db.get(Customer, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "客户不存在")
    scope = customer_scope_of(user, db)
    assert_scoped(obj, scope, db)
    return ok(mask_sensitive(CustomerOut.model_validate(obj).model_dump(), scope))


@router.put("/{cid}")
def update_customer(
    cid: int,
    body: CustomerUpdate,
    user: SysUser = Depends(require_permission("customer:write")),
    db: Session = Depends(get_db),
):
    obj = db.get(Customer, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "客户不存在")
    before = {k: getattr(obj, k) for k in body.model_dump(exclude_unset=True)}
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"customer:{cid}", before=str(before), after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(CustomerOut.model_validate(obj).model_dump())


@router.delete("/{cid}")
def delete_customer(
    cid: int,
    user: SysUser = Depends(require_permission("customer:delete")),
    db: Session = Depends(get_db),
):
    obj = db.get(Customer, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "客户不存在")
    # 存在关联项目（合同）时禁止删除，给出友好提示而非数据库外键 500
    contract_count = db.query(Contract).filter(Contract.customer_id == cid).count()
    if contract_count:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"该客户下存在 {contract_count} 个项目/合同，请先删除或转移相关项目后再删除客户",
        )
    try:
        db.delete(obj)
        record(db, user_id=user.id, action="delete", resource=f"customer:{cid}")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "该客户仍有关联数据（服务对象/工单等），无法删除",
        ) from None
    return ok({"deleted": cid})
