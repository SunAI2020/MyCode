"""变更单单测：冲突检测 + 状态机。"""
import pytest

from app.models import ChangeOrder
from app.services.change_service import detect_conflict, set_conflict_flag, transition_status


def _mk(db, ci_id, status="草稿"):
    o = ChangeOrder(ci_id=ci_id, status=status)
    db.add(o)
    db.flush()
    return o


def test_detect_conflict_same_ci(db):
    a = _mk(db, ci_id=1, status="待审批")
    b = _mk(db, ci_id=1, status="已批准")
    _mk(db, ci_id=2, status="待审批")  # 不同 CI，不冲突
    db.commit()

    conflicts = detect_conflict(db, ci_id=1, exclude_id=a.id)
    assert [c.id for c in conflicts] == [b.id]


def test_set_conflict_flag(db):
    a = _mk(db, ci_id=1, status="实施中")
    db.commit()
    b = _mk(db, ci_id=1, status="待审批")
    set_conflict_flag(db, b)
    assert b.conflict_flag is True


def test_transition_status_invalid(db):
    o = _mk(db, ci_id=1, status="草稿")
    with pytest.raises(ValueError):
        transition_status(db, o, "已完成")  # 草稿 不能直接完成
