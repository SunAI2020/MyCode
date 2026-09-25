"""问题整改闭环业务逻辑。"""
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Issue, Rectification, RectificationRecord


def create_rectification(
    db: Session, issue_id: int, plan: str, deadline: date | None, assignee: int | None
) -> Rectification:
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise ValueError("问题不存在")
    rect = Rectification(issue_id=issue_id, plan=plan, deadline=deadline, assignee=assignee, status="整改中")
    db.add(rect)
    if issue.status == "待整改":
        issue.status = "整改中"
    db.flush()
    return rect


def submit_round(
    db: Session, rectification_id: int, action: str, executor: int | None, effect: str
) -> RectificationRecord:
    """提交整改轮次：效果=通过 → 整改通过；否则自动下一轮。"""
    rect = db.get(Rectification, rectification_id)
    if rect is None:
        raise ValueError("整改不存在")
    if rect.status == "已通过":
        raise ValueError("整改已通过，不可再提交轮次")
    round_no = (
        db.query(func.max(RectificationRecord.round_no))
        .filter_by(rectification_id=rectification_id)
        .scalar()
        or 0
    ) + 1
    rec = RectificationRecord(
        rectification_id=rectification_id,
        round_no=round_no,
        action=action,
        executor=executor,
        effect=effect,
    )
    db.add(rec)
    if effect == "通过":
        rect.status = "已通过"
        _maybe_close_issue(db, rect.issue_id)
    else:
        rect.status = "整改中"  # 不通过/部分完成 → 继续下一轮
    db.flush()
    return rec


def _maybe_close_issue(db: Session, issue_id: int) -> None:
    remaining = (
        db.query(Rectification)
        .filter(Rectification.issue_id == issue_id, Rectification.status != "已通过")
        .count()
    )
    if remaining == 0:
        issue = db.get(Issue, issue_id)
        if issue is not None:
            issue.status = "已关闭"
