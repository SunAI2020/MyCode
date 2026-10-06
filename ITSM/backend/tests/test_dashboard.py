"""数据看板单测：聚合统计字段完整。"""
from app.api.v1.dashboard import dashboard
from app.models import Contract, Customer, SysRole, SysUser, SysUserRole, WorkOrder


def _mk_user(db):
    role = db.query(SysRole).filter_by(code="ticket_mgr").first()
    if role is None:
        role = SysRole(code="ticket_mgr", name="工单管理", scope="platform")
        db.add(role)
        db.flush()
    u = SysUser(username="mgr", name="管理", pwd_hash="x")
    db.add(u)
    db.flush()
    db.add(SysUserRole(user_id=u.id, role_id=role.id))
    db.commit()
    return u


def test_dashboard(db):
    u = _mk_user(db)
    c = Customer(name="A")
    db.add(c)
    db.flush()
    db.add(Contract(customer_id=c.id, name="x", status="执行中"))
    db.add(WorkOrder(no="WO-2026-0001", type="客户工单", status="待派单"))
    db.commit()

    data = dashboard(user=u, db=db)["data"]
    assert data["customers"] == 1
    assert data["contracts"]["total"] == 1
    assert data["contracts"]["by_status"]["执行中"] == 1
    assert data["work_orders"]["total"] == 1
    assert data["work_orders"]["by_status"]["待派单"] == 1
    assert data["deliveries"]["total"] == 0
    assert data["outsourcing"]["total"] == 0
    assert data["performance_top"] == []

    # 三行看板图表字段
    assert data["customers_by_industry"] == [{"name": "未分类", "value": 1}]
    assert data["contracts_by_status"] == [{"name": "执行中", "value": 1}]
    assert data["work_orders_by_status"] == [{"name": "待派单", "value": 1}]
    assert data["engineer_workload"]["categories"] == []
    assert data["dispatch_warning_by_customer"] == {
        "categories": ["未分配"],
        "series": [{"name": "待派单", "data": [1]}],
    }
    assert data["acceptance_warning_by_customer"]["categories"] == []
    assert data["schedule_warning_by_customer"]["categories"] == []
    assert data["personnel_forecast"]["categories"] == []
    assert data["issue_by_type_level"]["categories"] == []
    assert data["issue_by_type_status"]["categories"] == []
    assert data["compliance_by_reg_source"]["categories"] == []
    assert data["check_by_customer"]["categories"] == []
    assert data["coverage_by_customer"]["categories"] == []
    assert data["risk_by_customer"]["categories"] == []
