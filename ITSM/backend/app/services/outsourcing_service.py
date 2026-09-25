"""外包协作业务逻辑：状态机（接入可配置工作流引擎）。"""
from sqlalchemy.orm import Session

from app.models import Outsourcing
from app.services.workflow_service import assert_transition, log_transition


def transition_status(
    db: Session,
    outsourcing: Outsourcing,
    target: str,
    operator_id: int | None = None,
    note: str | None = None,
) -> Outsourcing:
    """校验并执行外包任务状态流转（接入可配置工作流引擎，全量留痕）。"""
    assert_transition(db, "outsourcing", outsourcing.status, target)
    if target == outsourcing.status:
        return outsourcing
    before = outsourcing.status
    outsourcing.status = target
    log_transition(
        db,
        entity="outsourcing",
        entity_id=outsourcing.id,
        from_status=before,
        to_status=target,
        operator_id=operator_id,
        note=note,
    )
    db.flush()
    return outsourcing
