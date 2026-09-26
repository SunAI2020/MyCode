"""驻场人员清单单测：添加/列表/换岗。"""
from app.api.v1.onsite import create_assignment, list_assignments, update_assignment
from app.models import Contract, Customer, OnsiteService, SysUser
from app.schemas.onsite import OnsiteAssignmentCreate, OnsiteAssignmentUpdate


def _mk(db):
    c = Customer(name="A")
    db.add(c)
    db.flush()
    ct = Contract(customer_id=c.id, name="x")
    db.add(ct)
    db.flush()
    os = OnsiteService(contract_id=ct.id, customer_id=c.id, headcount=2)
    db.add(os)
    db.flush()
    u = SysUser(username="staff", name="安服", pwd_hash="x")
    db.add(u)
    db.commit()
    return os, u


def test_create_assignment(db):
    os, u = _mk(db)
    data = create_assignment(
        OnsiteAssignmentCreate(onsite_id=os.id, user_id=u.id), user=u, db=db
    )["data"]
    assert data["status"] == "在岗"
    assert data["user_id"] == u.id


def test_list_assignments(db):
    os, u = _mk(db)
    create_assignment(OnsiteAssignmentCreate(onsite_id=os.id, user_id=u.id), user=u, db=db)
    data = list_assignments(onsite_id=os.id, user=u, db=db)["data"]
    assert len(data) == 1


def test_update_assignment_offduty(db):
    os, u = _mk(db)
    a = create_assignment(
        OnsiteAssignmentCreate(onsite_id=os.id, user_id=u.id), user=u, db=db
    )["data"]
    data = update_assignment(a["id"], OnsiteAssignmentUpdate(status="离岗"), user=u, db=db)["data"]
    assert data["status"] == "离岗"  # 换岗：离岗
