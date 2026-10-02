"""合同 / 业务系统(CI) / 合同子项 CRUD。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import (
    assert_scoped,
    customer_scope_of,
    get_current_user,
    get_db,
    require_permission,
    scope_filter,
)
from app.models import CmdbCi, CmdbCiDependency, Contract, ContractArchive, ContractItem, Customer, ServiceCycle, SysUser
from app.core.security import mask_sensitive, masked_page
from app.schemas.cmdb import CmdbCiDependencyCreate, CmdbCiDependencyOut
from app.schemas.contract import (
    CmdbCiCreate,
    CmdbCiOut,
    CmdbCiUpdate,
    ContractCreate,
    ContractItemCreate,
    ContractItemOut,
    ContractItemUpdate,
    ContractOut,
    ContractUpdate,
)
from app.services.audit_service import record
from app.services.cycle_service import generate_cycles
from app.utils.pagination import paginate
from app.utils.response import ok

contracts = APIRouter(prefix="/contracts", tags=["合同"])
items = APIRouter(prefix="/contract-items", tags=["合同子项"])
cis = APIRouter(prefix="/cmdb-cis", tags=["业务系统"])


# ---- 合同 ----
@contracts.get("")
def list_contracts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    q = scope_filter(db.query(Contract), Contract, scope)
    result = paginate(q, page, size, ContractOut)
    # 附上每个项目的合同原件数量，供前端灰显「无原件」项目的查看按钮
    ids = [it["id"] for it in result["items"]]
    if ids:
        counts = dict(
            db.query(ContractArchive.contract_id, func.count(ContractArchive.id))
            .filter(ContractArchive.contract_id.in_(ids))
            .group_by(ContractArchive.contract_id)
            .all()
        )
        for it in result["items"]:
            it["archive_count"] = counts.get(it["id"], 0)
    return ok(masked_page(result, scope))


@contracts.post("")
def create_contract(
    body: ContractCreate,
    user: SysUser = Depends(require_permission("contract:write")),
    db: Session = Depends(get_db),
):
    if db.get(Customer, body.customer_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "客户不存在")
    scope = customer_scope_of(user, db)
    if scope is not None and body.customer_id != scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户创建合同")
    obj = Contract(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"contract:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(ContractOut.model_validate(obj).model_dump())


@contracts.get("/{cid}")
def get_contract(cid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.get(Contract, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "合同不存在")
    scope = customer_scope_of(user, db)
    assert_scoped(obj, scope, db)
    return ok(mask_sensitive(ContractOut.model_validate(obj).model_dump(), scope))


@contracts.put("/{cid}")
def update_contract(
    cid: int,
    body: ContractUpdate,
    user: SysUser = Depends(require_permission("contract:write")),
    db: Session = Depends(get_db),
):
    obj = db.get(Contract, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "合同不存在")
    data = body.model_dump(exclude_unset=True)
    if data.get("customer_id") is not None:
        if db.get(Customer, data["customer_id"]) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "客户不存在")
        scope = customer_scope_of(user, db)
        if scope is not None and data["customer_id"] != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户修改合同")
    before = {k: getattr(obj, k) for k in data}
    for k, v in data.items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"contract:{cid}", before=str(before), after=str(data))
    db.commit()
    return ok(ContractOut.model_validate(obj).model_dump())


@contracts.delete("/{cid}")
def delete_contract(cid: int, user: SysUser = Depends(require_permission("contract:delete")), db: Session = Depends(get_db)):
    obj = db.get(Contract, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "合同不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"contract:{cid}")
    db.commit()
    return ok({"deleted": cid})


# ---- 合同子项 ----
@items.get("")
def list_items(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    contract_id: int | None = Query(None),
    ci_id: int | None = Query(None),
    ci_ids: str | None = Query(None),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    q = scope_filter(db.query(ContractItem), ContractItem, scope)
    if contract_id is not None:
        q = q.filter(ContractItem.contract_id == contract_id)
    if ci_id is not None:
        q = q.filter(ContractItem.ci_id == ci_id)
    if ci_ids:
        ids = [int(x) for x in ci_ids.split(",") if x.strip()]
        if ids:
            q = q.filter(ContractItem.ci_id.in_(ids))
    data = paginate(q, page, size, ContractItemOut)
    # 富化周期数量（供前端禁用「生成周期」按钮）
    item_ids = [it["id"] for it in data["items"]]
    if item_ids:
        counts = dict(
            db.query(ServiceCycle.contract_item_id, func.count(ServiceCycle.id))
            .filter(ServiceCycle.contract_item_id.in_(item_ids))
            .group_by(ServiceCycle.contract_item_id)
            .all()
        )
        for it in data["items"]:
            it["cycle_count"] = counts.get(it["id"], 0)
    return ok(masked_page(data, scope))


@items.post("")
def create_item(
    body: ContractItemCreate,
    user: SysUser = Depends(require_permission("contract:write")),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    if body.ci_id is not None:
        ci = db.get(CmdbCi, body.ci_id)
        if ci is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "业务系统不存在")
        if scope is not None and ci.customer_id != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户创建服务类别")
        contract_id = ci.contract_id
    else:
        if body.contract_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "未关联业务系统时需指定项目")
        contract = db.get(Contract, body.contract_id)
        if contract is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "项目不存在")
        if scope is not None and contract.customer_id != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户创建服务类别")
        contract_id = contract.id
    # 重复校验：同一客户 + 同一业务系统 + 同一服务类别
    if body.ci_id is not None:
        dup = db.query(ContractItem).filter(
            ContractItem.contract_id == contract_id,
            ContractItem.ci_id == body.ci_id,
            ContractItem.project == body.project,
        ).first()
        if dup is not None:
            ci = db.get(CmdbCi, body.ci_id)
            contract = db.get(Contract, contract_id)
            customer = db.get(Customer, contract.customer_id) if contract else None
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{customer.name if customer else ''}客户的{ci.name if ci else ''}业务系统，已经存在{body.project}服务类别，请勿重复提交！",
            )
    data = body.model_dump()
    data["contract_id"] = contract_id
    obj = ContractItem(**data)
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"contract_item:{obj.id}", after=str(data))
    db.commit()
    return ok(ContractItemOut.model_validate(obj).model_dump())


@items.get("/{iid}")
def get_item(iid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.get(ContractItem, iid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "子项不存在")
    scope = customer_scope_of(user, db)
    assert_scoped(obj, scope, db)
    return ok(mask_sensitive(ContractItemOut.model_validate(obj).model_dump(), scope))


@items.put("/{iid}")
def update_item(
    iid: int,
    body: ContractItemUpdate,
    user: SysUser = Depends(require_permission("contract:write")),
    db: Session = Depends(get_db),
):
    obj = db.get(ContractItem, iid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "子项不存在")
    data = body.model_dump(exclude_unset=True)
    if data.get("ci_id") is not None:
        ci = db.get(CmdbCi, data["ci_id"])
        if ci is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "业务系统不存在")
        scope = customer_scope_of(user, db)
        if scope is not None and ci.customer_id != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该业务系统")
        data["contract_id"] = ci.contract_id
    before = {k: getattr(obj, k) for k in data}
    for k, v in data.items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"contract_item:{iid}", before=str(before), after=str(data))
    db.commit()
    return ok(ContractItemOut.model_validate(obj).model_dump())


@items.delete("/{iid}")
def delete_item(iid: int, user: SysUser = Depends(require_permission("contract:delete")), db: Session = Depends(get_db)):
    obj = db.get(ContractItem, iid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "子项不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"contract_item:{iid}")
    db.commit()
    return ok({"deleted": iid})


@items.post("/{iid}/cycles/generate")
def generate_item_cycles(
    iid: int,
    user: SysUser = Depends(require_permission("contract:write")),
    db: Session = Depends(get_db),
):
    item = db.get(ContractItem, iid)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "子项不存在")
    # 重复检测：该子项已生成过周期 → 返回 duplicate 标志，由前端弹框提示，不重复生成
    if db.query(ServiceCycle).filter(ServiceCycle.contract_item_id == iid).first() is not None:
        ci = db.get(CmdbCi, item.ci_id) if item.ci_id else None
        contract = db.get(Contract, item.contract_id)
        customer = db.get(Customer, contract.customer_id) if contract else None
        return ok({
            "duplicate": True,
            "message": f"{customer.name if customer else ''}的{ci.name if ci else '//'}业务系统，已经存在{item.project}服务周期，请勿重复提交！",
        })
    try:
        result = generate_cycles(db, iid)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    result["duplicate"] = False
    record(db, user_id=user.id, action="generate_cycles", resource=f"contract_item:{iid}", after=str(result))
    db.commit()
    return ok(result)


# ---- 业务系统 CI ----
@cis.get("")
def list_cis(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    customer_id: int | None = Query(None),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    q = scope_filter(db.query(CmdbCi), CmdbCi, scope)
    if customer_id is not None:
        q = q.filter(CmdbCi.customer_id == customer_id)
    return ok(masked_page(paginate(q, page, size, CmdbCiOut), scope))


@cis.post("")
def create_ci(
    body: CmdbCiCreate,
    user: SysUser = Depends(require_permission("contract:write")),
    db: Session = Depends(get_db),
):
    contract = db.get(Contract, body.contract_id)
    if contract is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "合同不存在")
    scope = customer_scope_of(user, db)
    if scope is not None and contract.customer_id != scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户创建业务系统")
    data = body.model_dump()
    data["customer_id"] = contract.customer_id
    obj = CmdbCi(**data)
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"cmdb_ci:{obj.id}", after=str(data))
    db.commit()
    return ok(CmdbCiOut.model_validate(obj).model_dump())


@cis.get("/{iid}")
def get_ci(iid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.get(CmdbCi, iid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "业务系统不存在")
    scope = customer_scope_of(user, db)
    assert_scoped(obj, scope, db)
    return ok(mask_sensitive(CmdbCiOut.model_validate(obj).model_dump(), scope))


@cis.put("/{iid}")
def update_ci(
    iid: int,
    body: CmdbCiUpdate,
    user: SysUser = Depends(require_permission("contract:write")),
    db: Session = Depends(get_db),
):
    obj = db.get(CmdbCi, iid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "业务系统不存在")
    data = body.model_dump(exclude_unset=True)
    if data.get("contract_id") is not None and data["contract_id"] != obj.contract_id:
        contract = db.get(Contract, data["contract_id"])
        if contract is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "合同不存在")
        scope = customer_scope_of(user, db)
        if scope is not None and contract.customer_id != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该合同")
        data["customer_id"] = contract.customer_id
        # 业务系统换合同后，同步其子服务类别的冗余 contract_id，维持「contract_id = ci.contract_id」不变量
        db.query(ContractItem).filter(ContractItem.ci_id == iid).update({ContractItem.contract_id: contract.id})
    before = {k: getattr(obj, k) for k in data}
    for k, v in data.items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"cmdb_ci:{iid}", before=str(before), after=str(data))
    db.commit()
    return ok(CmdbCiOut.model_validate(obj).model_dump())


@cis.delete("/{iid}")
def delete_ci(iid: int, user: SysUser = Depends(require_permission("contract:delete")), db: Session = Depends(get_db)):
    obj = db.get(CmdbCi, iid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "业务系统不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"cmdb_ci:{iid}")
    db.commit()
    return ok({"deleted": iid})


# ---- 依赖拓扑 ----
dependencies = APIRouter(prefix="/cmdb-ci-dependencies", tags=["依赖拓扑"])


@dependencies.post("")
def create_dependency(
    body: CmdbCiDependencyCreate,
    user: SysUser = Depends(require_permission("contract:write")),
    db: Session = Depends(get_db),
):
    src = db.get(CmdbCi, body.source_ci_id)
    dst = db.get(CmdbCi, body.target_ci_id)
    if src is None or dst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "业务系统不存在")
    assert_scoped(src, customer_scope_of(user, db), db)  # 校验调用方归属
    if src.customer_id != dst.customer_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "不能跨客户建立依赖")
    obj = CmdbCiDependency(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"cmdb_ci_dependency:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(CmdbCiDependencyOut.model_validate(obj).model_dump())


@dependencies.delete("/{did}")
def delete_dependency(did: int, user: SysUser = Depends(require_permission("contract:write")), db: Session = Depends(get_db)):
    obj = db.get(CmdbCiDependency, did)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "依赖不存在")
    src = db.get(CmdbCi, obj.source_ci_id)
    assert_scoped(src, customer_scope_of(user, db), db)
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"cmdb_ci_dependency:{did}")
    db.commit()
    return ok({"deleted": did})


@cis.get("/{iid}/dependencies")
def list_dependencies(iid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.get(CmdbCi, iid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "业务系统不存在")
    assert_scoped(obj, customer_scope_of(user, db), db)
    rows = db.query(CmdbCiDependency).filter(
        (CmdbCiDependency.source_ci_id == iid) | (CmdbCiDependency.target_ci_id == iid)
    ).all()
    return ok([CmdbCiDependencyOut.model_validate(r).model_dump() for r in rows])


@cis.get("/{iid}/impact")
def impact_analysis(iid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """影响分析：返回该 CI 故障时受影响的上游 CI（递归，含直接/间接依赖方）。"""
    obj = db.get(CmdbCi, iid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "业务系统不存在")
    assert_scoped(obj, customer_scope_of(user, db), db)
    # BFS 递归上游：谁依赖我（source 依赖 target=我）
    affected: list[int] = []
    frontier = [iid]
    seen = {iid}
    while frontier:
        cur = frontier.pop(0)
        deps = db.query(CmdbCiDependency).filter(CmdbCiDependency.target_ci_id == cur).all()
        for d in deps:
            if d.source_ci_id not in seen:
                seen.add(d.source_ci_id)
                affected.append(d.source_ci_id)
                frontier.append(d.source_ci_id)
    return ok({"affected_ci_ids": affected})
