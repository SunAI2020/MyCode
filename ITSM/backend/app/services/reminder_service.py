"""服务提醒。"""
from sqlalchemy.orm import Session

from app.models import ServiceReminder


def create_reminder(
    db: Session,
    *,
    cycle_id: int | None,
    type_: str,
    level: str,
    content: str,
    to_user_id: int | None = None,
    channel: str = "站内",
) -> ServiceReminder:
    r = ServiceReminder(
        cycle_id=cycle_id,
        type=type_,
        level=level,
        content=content,
        to_user_id=to_user_id,
        channel=channel,
    )
    db.add(r)
    return r
