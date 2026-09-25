"""问题整改闭环单测。"""
from datetime import date

import pytest

from app.models import Issue, Rectification, RectificationRecord, WorkOrder
from app.services.issue_service import create_rectification, submit_round


def _mk_issue(db) -> Issue:
    wo = WorkOrder(no="WO-2026-0001", type="客户工单")
    db.add(wo)
    db.flush()
    issue = Issue(work_order_id=wo.id, description="发现漏洞", status="待整改")
    db.add(issue)
    db.commit()
    return issue


def test_rectification_pass_closes_issue(db):
    issue = _mk_issue(db)
    rect = create_rectification(db, issue.id, "修复漏洞", date(2024, 1, 31), assignee=1)
    db.commit()
    assert rect.status == "整改中"
    assert db.get(Issue, issue.id).status == "整改中"

    rec = submit_round(db, rect.id, "已修复", executor=1, effect="通过")
    db.commit()
    assert rec.round_no == 1
    assert db.get(Rectification, rect.id).status == "已通过"
    assert db.get(Issue, issue.id).status == "已关闭"


def test_rectification_failed_next_round(db):
    issue = _mk_issue(db)
    rect = create_rectification(db, issue.id, "修复", None, 1)
    db.commit()
    submit_round(db, rect.id, "第一次尝试", 1, "不通过")
    db.commit()
    submit_round(db, rect.id, "第二次尝试", 1, "部分完成")
    db.commit()
    records = db.query(RectificationRecord).filter_by(rectification_id=rect.id).all()
    assert [r.round_no for r in records] == [1, 2]
    assert db.get(Rectification, rect.id).status == "整改中"


def test_submit_after_pass_raises(db):
    issue = _mk_issue(db)
    rect = create_rectification(db, issue.id, "修复", None, 1)
    db.commit()
    submit_round(db, rect.id, "done", 1, "通过")
    db.commit()
    with pytest.raises(ValueError):
        submit_round(db, rect.id, "again", 1, "通过")


def test_rectification_pass_closes_issue_autoflush_off():
    """复现生产 autoflush=False：最后一轮整改通过后问题必须关闭。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.models  # noqa: F401
    from app.db.base import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    s = Session()
    try:
        wo = WorkOrder(no="WO-2026-0001", type="客户工单")
        s.add(wo)
        s.flush()
        issue = Issue(work_order_id=wo.id, description="x", status="待整改")
        s.add(issue)
        s.flush()
        rect = create_rectification(s, issue.id, "修复", None, 1)
        s.commit()
        submit_round(s, rect.id, "done", 1, "通过")
        s.commit()
        assert s.get(Issue, issue.id).status == "已关闭"
    finally:
        s.close()
        engine.dispose()
