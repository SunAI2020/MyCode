"""驻场服务业务逻辑：日报周/月报聚合。"""
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import OnsiteDailyReport


def summarize_reports(
    db: Session,
    onsite_id: int,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    """按 work_type 聚合日报条数，输出周/月报统计。"""
    q = (
        db.query(
            OnsiteDailyReport.work_type,
            func.count(OnsiteDailyReport.id).label("cnt"),
        )
        .filter(OnsiteDailyReport.onsite_id == onsite_id)
    )
    if start is not None:
        q = q.filter(OnsiteDailyReport.report_date >= start)
    if end is not None:
        q = q.filter(OnsiteDailyReport.report_date <= end)
    q = q.group_by(OnsiteDailyReport.work_type)
    by_type = [{"work_type": w, "count": int(c)} for w, c in q.all()]
    return {
        "onsite_id": onsite_id,
        "start": str(start) if start else None,
        "end": str(end) if end else None,
        "total": sum(x["count"] for x in by_type),
        "by_type": by_type,
    }
