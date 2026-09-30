"""问题整改闭环业务逻辑。"""
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ComplianceCheck, Issue, Rectification, RectificationRecord

from app.services.evidence_service import collect_for_rectification


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
        # 合规证据自动采集：整改通过 → 匹配 issue 挂接的合规要求生成证据（步骤 51）
        collect_for_rectification(db, rect, operator_id=executor)
    else:
        rect.status = "整改中"  # 不通过/部分完成 → 继续下一轮
    db.flush()
    return rec


def _maybe_close_issue(db: Session, issue_id: int) -> None:
    # 生产 SessionLocal 为 autoflush=False，须先 flush 使 rect.status 的待写变更落库，
    # 否则下方 count 读到陈旧「整改中」，导致最后一个整改通过后问题仍不关闭。
    db.flush()
    remaining = (
        db.query(Rectification)
        .filter(Rectification.issue_id == issue_id, Rectification.status != "已通过")
        .count()
    )
    if remaining == 0:
        issue = db.get(Issue, issue_id)
        if issue is not None:
            issue.status = "已关闭"
            _maybe_close_compliance_check(db, issue)


def _maybe_close_compliance_check(db: Session, issue: Issue) -> None:
    """合规闭环回写：该合规要求关联的 issue 全部关闭 → 核验置「已闭环」（步骤 51）。"""
    if issue.requirement_id is None:
        return
    open_issues = (
        db.query(Issue)
        .filter(Issue.requirement_id == issue.requirement_id, Issue.status != "已关闭")
        .count()
    )
    if open_issues == 0:
        checks = (
            db.query(ComplianceCheck)
            .filter(
                ComplianceCheck.requirement_id == issue.requirement_id,
                ComplianceCheck.status == "有缺口",
            )
            .all()
        )
        for c in checks:
            c.status = "已闭环"
