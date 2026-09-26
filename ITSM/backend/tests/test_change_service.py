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


def test_set_conflict_flag_symmetric(db):
    a = _mk(db, ci_id=1, status="已批准")
    b = _mk(db, ci_id=1, status="实施中")
    db.commit()
    set_conflict_flag(db, a)
    assert a.conflict_flag is True
    assert b.conflict_flag is True  # 对称：同 CI 既有活跃变更也一并标记


def test_set_conflict_flag_clears_stale_on_ci_change(db):
    a = _mk(db, ci_id=1, status="已批准")
    b = _mk(db, ci_id=1, status="实施中")
    db.commit()
    set_conflict_flag(db, a)
    assert b.conflict_flag is True  # 同 CI-1 冲突

    # 将 a 移到 CI-2：旧 CI-1 上 b 的冲突标记应解除，不再残留过期冲突
    a.ci_id = 2
    set_conflict_flag(db, a, previous_ci_id=1)
    assert a.conflict_flag is False  # CI-2 上只有 a 自己
    assert b.conflict_flag is False  # CI-1 上只剩 b 自己，无冲突
