"""合规证据采集：把现有履约动作自动映射为合规证据（步骤 51）。

与 audit_service.record 同模式：只 add 不 commit，由调用方统一提交。
"""
import hashlib
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (
    Approval,
    ChangeOrder,
    CmdbCi,
    ComplianceEvidence,
    ComplianceRequirement,
    Contract,
    ContractItem,
    Delivery,
    Issue,
    WorkOrder,
    WorkOrderItem,
)


def _hash(source_type: str, source_id: int) -> str:
    """自动证据的内容哈希：源实体标识的 SHA-256（防篡改锚点）。"""
    return hashlib.sha256(f"{source_type}:{source_id}".encode("utf-8")).hexdigest()


def _chain_hash(
    prev_hash: str | None, content_hash: str | None, source_type: str, source_id: int | None
) -> str:
    """链式哈希：SHA256(prev_hash | content_hash | source_type | source_id)。"""
    payload = "|".join(
        [
            prev_hash or "",
            content_hash or "",
            source_type or "",
            str(source_id) if source_id is not None else "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _latest_chain_hash(db: Session, requirement_id: int) -> str | None:
    row = (
        db.query(ComplianceEvidence.chain_hash)
        .filter(ComplianceEvidence.requirement_id == requirement_id)
        .order_by(ComplianceEvidence.id.desc())
        .first()
    )
    return row[0] if row else None


def collect(
    db: Session,
    *,
    requirement_id: int,
    source_type: str,
    source_id: int | None = None,
    evidence_type: str = "自动",
    operator_id: int | None = None,
    content_hash: str | None = None,
    note: str | None = None,
    occurred_at: datetime | None = None,
) -> ComplianceEvidence:
    """生成一条合规证据（不 commit）。P4：按同要求下上一条证据做链式哈希防篡改。"""
    if occurred_at is None:
        occurred_at = datetime.now()
    prev_hash = _latest_chain_hash(db, requirement_id)
    chain_hash = _chain_hash(prev_hash, content_hash, source_type, source_id)
    ev = ComplianceEvidence(
        requirement_id=requirement_id,
        source_type=source_type,
        source_id=source_id,
        evidence_type=evidence_type,
        operator_id=operator_id,
        content_hash=content_hash,
        prev_hash=prev_hash,
        chain_hash=chain_hash,
        note=note,
        occurred_at=occurred_at,
    )
    db.add(ev)
    return ev


def verify_chain(db: Session, requirement_id: int) -> dict:
    """验证某合规要求下证据哈希链是否完整。返回 {intact, total, broken_ids}。"""
    rows = (
        db.query(ComplianceEvidence)
        .filter(ComplianceEvidence.requirement_id == requirement_id)
        .order_by(ComplianceEvidence.id.asc())
        .all()
    )
    prev = None
    broken_ids: list[int] = []
    for e in rows:
        expected = _chain_hash(prev, e.content_hash, e.source_type, e.source_id)
        if e.chain_hash != expected:
            broken_ids.append(e.id)
        prev = e.chain_hash
    return {"intact": not broken_ids, "total": len(rows), "broken_ids": broken_ids}


def collect_for_work_order(db: Session, work_order: WorkOrder, operator_id: int | None = None) -> int:
    """工单完成自动采集：匹配工单关联服务项目对应的合规要求，逐条生成证据。返回生成数。"""
    item_ids: set[int] = set()
    if work_order.contract_item_id:
        item_ids.add(work_order.contract_item_id)
    for rel in db.query(WorkOrderItem).filter_by(work_order_id=work_order.id).all():
        item_ids.add(rel.contract_item_id)
    if not item_ids:
        return 0

    # 归集服务项目所属客户，作为租户过滤（防止跨客户误采集证据）
    customer_ids = {
        cid
        for (cid,) in db.query(Contract.customer_id)
        .join(ContractItem, ContractItem.contract_id == Contract.id)
        .filter(ContractItem.id.in_(item_ids))
        .all()
    }
    if not customer_ids:
        return 0

    reqs = (
        db.query(ComplianceRequirement)
        .filter(
            ComplianceRequirement.source_type == "服务项目",
            ComplianceRequirement.source_id.in_(item_ids),
            ComplianceRequirement.customer_id.in_(customer_ids),
            ComplianceRequirement.status == "启用",
        )
        .all()
    )
    for r in reqs:
        collect(
            db,
            requirement_id=r.id,
            source_type="工单",
            source_id=work_order.id,
            evidence_type="自动",
            operator_id=operator_id,
            content_hash=_hash("工单", work_order.id),
        )
    return len(reqs)


def collect_for_rectification(
    db: Session, rectification, operator_id: int | None = None
) -> int:
    """整改通过自动采集：匹配 issue 挂接的合规要求，生成证据。返回生成数（0/1）。"""
    issue = db.get(Issue, rectification.issue_id)
    if issue is None or issue.requirement_id is None:
        return 0
    collect(
        db,
        requirement_id=issue.requirement_id,
        source_type="整改",
        source_id=rectification.id,
        evidence_type="自动",
        operator_id=operator_id,
        content_hash=_hash("整改", rectification.id),
    )
    return 1


def _resolve_context(
    db: Session,
    *,
    contract_id: int | None = None,
    contract_item_id: int | None = None,
    work_order_id: int | None = None,
    ci_id: int | None = None,
) -> tuple[int | None, int | None, int | None]:
    """把变更/交付/审批等实体解析回 (customer_id, contract_id, contract_item_id)。

    实体未必直接带 customer_id，沿合同/工单/配置项链路向上归集。
    """
    customer_id: int | None = None
    if contract_id is not None:
        contract = db.get(Contract, contract_id)
        if contract is not None:
            customer_id = contract.customer_id
    if work_order_id is not None:
        wo = db.get(WorkOrder, work_order_id)
        if wo is not None:
            customer_id = customer_id or wo.customer_id
            contract_id = contract_id or wo.contract_id
            contract_item_id = contract_item_id or wo.contract_item_id
    if ci_id is not None and customer_id is None:
        ci = db.get(CmdbCi, ci_id)
        if ci is not None:
            customer_id = ci.customer_id
            contract_id = contract_id or ci.contract_id
    return customer_id, contract_id, contract_item_id


def _collect_matching(
    db: Session,
    *,
    customer_id: int,
    contract_id: int | None,
    contract_item_id: int | None,
    source_type: str,
    source_id: int,
    operator_id: int | None = None,
) -> int:
    """按「客户 + 项目/服务项目」维度匹配启用中的合规要求，逐条生成证据。返回生成数。"""
    q = db.query(ComplianceRequirement).filter(
        ComplianceRequirement.customer_id == customer_id,
        ComplianceRequirement.status == "启用",
    )
    conds = []
    if contract_id is not None:
        conds.append(ComplianceRequirement.project_id == contract_id)
    if contract_item_id is not None:
        conds.append(
            (ComplianceRequirement.source_type == "服务项目")
            & (ComplianceRequirement.source_id == contract_item_id)
        )
    if conds:
        q = q.filter(or_(*conds))
    else:
        # 无项目/服务项目上下文：仅匹配客户全局要求（project_id 为空）
        q = q.filter(ComplianceRequirement.project_id.is_(None))
    reqs = q.all()
    for r in reqs:
        collect(
            db,
            requirement_id=r.id,
            source_type=source_type,
            source_id=source_id,
            evidence_type="自动",
            operator_id=operator_id,
            content_hash=_hash(source_type, source_id),
        )
    return len(reqs)


def collect_for_change_order(db: Session, change_order: ChangeOrder, operator_id: int | None = None) -> int:
    """变更完成自动采集：匹配变更所属客户/项目的合规要求。"""
    customer_id, contract_id, contract_item_id = _resolve_context(
        db, work_order_id=change_order.work_order_id, ci_id=change_order.ci_id
    )
    if customer_id is None:
        return 0
    return _collect_matching(
        db,
        customer_id=customer_id,
        contract_id=contract_id,
        contract_item_id=contract_item_id,
        source_type="变更",
        source_id=change_order.id,
        operator_id=operator_id,
    )


def collect_for_delivery(db: Session, delivery: Delivery, operator_id: int | None = None) -> int:
    """交付签署自动采集：匹配交付所属客户/项目的合规要求。"""
    customer_id, contract_id, contract_item_id = _resolve_context(
        db,
        contract_id=delivery.contract_id,
        contract_item_id=delivery.contract_item_id,
        work_order_id=delivery.work_order_id,
    )
    if customer_id is None:
        return 0
    return _collect_matching(
        db,
        customer_id=customer_id,
        contract_id=contract_id,
        contract_item_id=contract_item_id,
        source_type="交付",
        source_id=delivery.id,
        operator_id=operator_id,
    )


def collect_for_approval(db: Session, approval: Approval, operator_id: int | None = None) -> int:
    """审批通过自动采集：按审批对象（工单/变更单）归集到客户/项目后匹配合规要求。"""
    customer_id = contract_id = contract_item_id = None
    if approval.entity == "work_order":
        customer_id, contract_id, contract_item_id = _resolve_context(
            db, work_order_id=approval.entity_id
        )
    elif approval.entity == "change_order":
        co = db.get(ChangeOrder, approval.entity_id)
        if co is not None:
            customer_id, contract_id, contract_item_id = _resolve_context(
                db, work_order_id=co.work_order_id, ci_id=co.ci_id
            )
    else:
        return 0
    if customer_id is None:
        return 0
    return _collect_matching(
        db,
        customer_id=customer_id,
        contract_id=contract_id,
        contract_item_id=contract_item_id,
        source_type="审批",
        source_id=approval.id,
        operator_id=operator_id,
    )
