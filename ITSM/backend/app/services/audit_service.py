"""操作审计：写操作落 sys_audit_log。"""
from sqlalchemy.orm import Session

from app.core.context import client_ip
from app.models import SysAuditLog


def record(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    resource: str | None = None,
    before: str | None = None,
    after: str | None = None,
    ip: str | None = None,
) -> None:
    """新增一条审计记录（不 commit，由调用方统一提交）。

    ip 缺省时取请求上下文中的客户端 IP（get_current_user 捕获），补全审计留痕。
    """
    if ip is None:
        ip = client_ip.get()
    db.add(
        SysAuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            before=before,
            after=after,
            ip=ip,
        )
    )
