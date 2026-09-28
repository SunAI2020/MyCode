"""CMDB 依赖拓扑单测：依赖管理 + 影响分析。"""
from app.api.v1.contracts import create_dependency, impact_analysis, list_dependencies
from app.models import CmdbCi, Contract, Customer, SysUser
from app.schemas.cmdb import CmdbCiDependencyCreate


def _mk_user(db):
    u = SysUser(username="admin", name="管理员", pwd_hash="x")
    db.add(u)
    db.commit()
    return u


def _mk_ci(db, name):
    c = db.query(Customer).filter_by(name="A").first()
    if c is None:
        c = Customer(name="A")
        db.add(c)
        db.flush()
    ct = db.query(Contract).filter_by(customer_id=c.id).first()
    if ct is None:
        ct = Contract(customer_id=c.id, name="合同")
        db.add(ct)
        db.flush()
    ci = CmdbCi(customer_id=c.id, contract_id=ct.id, name=name)
    db.add(ci)
    db.commit()
    return ci


def test_create_and_list_dependency(db):
    u = _mk_user(db)
    a = _mk_ci(db, "OA")
    b = _mk_ci(db, "DB")
    create_dependency(CmdbCiDependencyCreate(source_ci_id=a.id, target_ci_id=b.id), user=u, db=db)
    data = list_dependencies(a.id, user=u, db=db)["data"]
    assert len(data) == 1
    assert data[0]["source_ci_id"] == a.id
    assert data[0]["target_ci_id"] == b.id


def test_impact_analysis_recursive(db):
    u = _mk_user(db)
    a = _mk_ci(db, "OA")
    b = _mk_ci(db, "DB")
    c = _mk_ci(db, "Web")
    # OA 依赖 DB；Web 依赖 OA。DB 故障影响 OA 和 Web。
    create_dependency(CmdbCiDependencyCreate(source_ci_id=a.id, target_ci_id=b.id), user=u, db=db)
    create_dependency(CmdbCiDependencyCreate(source_ci_id=c.id, target_ci_id=a.id), user=u, db=db)

    data = impact_analysis(b.id, user=u, db=db)["data"]
    assert set(data["affected_ci_ids"]) == {a.id, c.id}
