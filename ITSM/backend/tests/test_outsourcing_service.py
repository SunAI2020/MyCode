"""外包协作单测：状态机。"""
import pytest

from app.models import Outsourcing, OutsourceUser
from app.services.outsourcing_service import transition_status


def _mk_outsourcing(db, status="待接单"):
    u = OutsourceUser(name="外包A")
    db.add(u)
    db.flush()
    o = Outsourcing(work_order_id=1, outsource_user_id=u.id, status=status)
    db.add(o)
    db.flush()
    return o


def test_transition_accept(db):
    o = _mk_outsourcing(db)
    transition_status(db, o, "已接单")
    assert o.status == "已接单"


def test_transition_verify_reject_back(db):
    o = _mk_outsourcing(db, status="待验收")
    transition_status(db, o, "已验收")
    assert o.status == "已验收"


def test_transition_invalid_raises(db):
    o = _mk_outsourcing(db)  # 待接单
    with pytest.raises(ValueError):
        transition_status(db, o, "已结算")  # 待接单 不能直接结算
