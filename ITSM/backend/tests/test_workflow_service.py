"""工作流引擎单测：默认流转 / DB 扩展 / 非法流转 / 全量留痕。"""
import pytest

from app.models import ActionLog, WorkflowRule
from app.services.workflow_service import (
    allowed_targets,
    assert_transition,
    can_transition,
    log_transition,
)


def test_default_work_order_targets(db):
    assert allowed_targets(db, "work_order", "待派单") == ["待执行", "已取消"]
    assert allowed_targets(db, "work_order", "待验收") == ["已验收", "已取消"]
    assert allowed_targets(db, "work_order", "已验收") == ["已结单"]
    assert allowed_targets(db, "work_order", "已结单") == ["已关闭"]
    assert allowed_targets(db, "work_order", "已取消") == ["已关闭"]
    assert allowed_targets(db, "work_order", "已关闭") == []


def test_db_rule_extends_default(db):
    db.add(WorkflowRule(entity="change_order", from_status="草稿", to_status="实施中", enabled=True))
    db.commit()
    targets = allowed_targets(db, "change_order", "草稿")
    assert "待审批" in targets  # 默认保留
    assert "实施中" in targets  # DB 扩展


def test_disabled_rule_ignored(db):
    db.add(WorkflowRule(entity="change_order", from_status="草稿", to_status="实施中", enabled=False))
    db.commit()
    assert "实施中" not in allowed_targets(db, "change_order", "草稿")


def test_can_transition_same_status(db):
    assert can_transition(db, "work_order", "执行中", "执行中") is True


def test_assert_transition_invalid_raises(db):
    with pytest.raises(ValueError):
        assert_transition(db, "work_order", "待派单", "已结单")


def test_log_transition_creates_action_log(db):
    log_transition(db, entity="work_order", entity_id=7, from_status="执行中", to_status="待验收", operator_id=3, note="自检通过")
    db.commit()
    log = db.query(ActionLog).one()
    assert log.entity == "work_order"
    assert log.entity_id == 7
    assert log.from_status == "执行中"
    assert log.to_status == "待验收"
    assert log.operator_id == 3
