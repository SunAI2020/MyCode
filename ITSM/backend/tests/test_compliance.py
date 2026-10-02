"""合规运营框架单测（步骤 51 · P1/P2）：证据自动采集 + 挂接闭环。"""
from app.models import (
    Approval,
    ChangeOrder,
    CmdbCi,
    ComplianceCheck,
    ComplianceEvidence,
    ComplianceRequirement,
    ComplianceRequirementTemplate,
    Contract,
    ContractItem,
    Customer,
    Delivery,
    Issue,
    Rectification,
    WorkOrder,
)
from app.db.regulatory_templates import TEMPLATES, seed_templates
from app.services.evidence_service import (
    collect,
    collect_for_approval,
    collect_for_change_order,
    collect_for_delivery,
    collect_for_rectification,
    collect_for_work_order,
    verify_chain,
)
from app.services.compliance_service import build_report_snapshot, compute_metrics
from app.services.issue_service import submit_round


def _mk_chain(db):
    """构造 客户→合同→业务系统→服务类别 基础链。"""
    c = Customer(name="A")
    db.add(c)
    db.flush()
    ct = Contract(customer_id=c.id, name="x")
    db.add(ct)
    db.flush()
    ci = CmdbCi(customer_id=c.id, contract_id=ct.id, name="CI")
    db.add(ci)
    db.flush()
    item = ContractItem(contract_id=ct.id, ci_id=ci.id, project="OA", frequency=1, unit="月")
    db.add(item)
    db.commit()
    return item


def test_collect_creates_evidence(db):
    item = _mk_chain(db)
    req = ComplianceRequirement(customer_id=item.contract_id, clause="要求A")
    db.add(req)
    db.commit()

    collect(db, requirement_id=req.id, source_type="人工", note="x")
    db.commit()

    rows = db.query(ComplianceEvidence).all()
    assert len(rows) == 1
    assert rows[0].requirement_id == req.id
    assert rows[0].evidence_type == "自动"


def test_collect_for_work_order(db):
    item = _mk_chain(db)
    req = ComplianceRequirement(
        customer_id=item.contract_id, source_type="服务类别", source_id=item.id, clause="要求A"
    )
    db.add(req)
    db.commit()
    wo = WorkOrder(no="WO-1", contract_item_id=item.id)
    db.add(wo)
    db.commit()

    n = collect_for_work_order(db, wo, operator_id=1)
    db.commit()

    assert n == 1
    rows = db.query(ComplianceEvidence).all()
    assert len(rows) == 1
    assert rows[0].source_type == "工单"
    assert rows[0].source_id == wo.id


def test_collect_for_work_order_no_match(db):
    item = _mk_chain(db)
    wo = WorkOrder(no="WO-2", contract_item_id=item.id)
    db.add(wo)
    db.commit()

    n = collect_for_work_order(db, wo)
    db.commit()

    assert n == 0
    assert db.query(ComplianceEvidence).count() == 0


def test_collect_for_rectification(db):
    item = _mk_chain(db)
    req = ComplianceRequirement(customer_id=item.contract_id, clause="要求A")
    db.add(req)
    db.flush()
    wo = WorkOrder(no="WO-3")
    db.add(wo)
    db.flush()
    issue = Issue(work_order_id=wo.id, description="x", requirement_id=req.id)
    db.add(issue)
    db.flush()
    rect = Rectification(issue_id=issue.id, plan="p")
    db.add(rect)
    db.commit()

    n = collect_for_rectification(db, rect, operator_id=1)
    db.commit()

    assert n == 1
    rows = db.query(ComplianceEvidence).all()
    assert len(rows) == 1
    assert rows[0].source_type == "整改"
    assert rows[0].source_id == rect.id


def test_collect_for_rectification_no_requirement(db):
    wo = WorkOrder(no="WO-4")
    db.add(wo)
    db.flush()
    issue = Issue(work_order_id=wo.id, description="x")
    db.add(issue)
    db.flush()
    rect = Rectification(issue_id=issue.id, plan="p")
    db.add(rect)
    db.commit()

    n = collect_for_rectification(db, rect)
    db.commit()

    assert n == 0
    assert db.query(ComplianceEvidence).count() == 0


def _mk_customer_contract(db):
    """构造 客户→合同 基础链，返回 (customer, contract)。"""
    c = Customer(name="A")
    db.add(c)
    db.flush()
    ct = Contract(customer_id=c.id, name="x")
    db.add(ct)
    db.commit()
    return c, ct


def test_collect_for_delivery(db):
    c, ct = _mk_customer_contract(db)
    req = ComplianceRequirement(customer_id=c.id, project_id=ct.id, clause="要求A")
    db.add(req)
    db.commit()
    d = Delivery(contract_id=ct.id, title="报告")
    db.add(d)
    db.commit()

    n = collect_for_delivery(db, d, operator_id=1)
    db.commit()

    assert n == 1
    ev = db.query(ComplianceEvidence).all()
    assert len(ev) == 1 and ev[0].source_type == "交付" and ev[0].source_id == d.id


def test_collect_for_change_order(db):
    c, ct = _mk_customer_contract(db)
    ci = CmdbCi(customer_id=c.id, contract_id=ct.id, name="CI")
    db.add(ci)
    db.flush()
    req = ComplianceRequirement(customer_id=c.id, project_id=ct.id, clause="要求A")
    db.add(req)
    db.commit()
    co = ChangeOrder(ci_id=ci.id)
    db.add(co)
    db.commit()

    n = collect_for_change_order(db, co, operator_id=1)
    db.commit()

    assert n == 1
    ev = db.query(ComplianceEvidence).all()
    assert len(ev) == 1 and ev[0].source_type == "变更" and ev[0].source_id == co.id


def test_collect_for_approval(db):
    c, ct = _mk_customer_contract(db)
    req = ComplianceRequirement(customer_id=c.id, project_id=ct.id, clause="要求A")
    db.add(req)
    db.flush()
    wo = WorkOrder(no="WO-5", customer_id=c.id, contract_id=ct.id)
    db.add(wo)
    db.flush()
    appr = Approval(entity="work_order", entity_id=wo.id, from_status="待派单", to_status="进行中", applicant_id=1)
    db.add(appr)
    db.commit()

    n = collect_for_approval(db, appr, operator_id=1)
    db.commit()

    assert n == 1
    ev = db.query(ComplianceEvidence).all()
    assert len(ev) == 1 and ev[0].source_type == "审批" and ev[0].source_id == appr.id


def test_close_issue_closes_check(db):
    """核验有缺口 → 整改通过问题关闭 → 核验自动置「已闭环」（步骤 51 闭环回写）。"""
    req = ComplianceRequirement(customer_id=1, clause="要求A")
    db.add(req)
    db.flush()
    wo = WorkOrder(no="WO-6")
    db.add(wo)
    db.flush()
    issue = Issue(work_order_id=wo.id, description="x", requirement_id=req.id)
    db.add(issue)
    db.flush()
    check = ComplianceCheck(requirement_id=req.id, status="有缺口", issue_id=issue.id)
    db.add(check)
    db.flush()
    rect = Rectification(issue_id=issue.id, plan="p")
    db.add(rect)
    db.commit()

    submit_round(db, rect.id, "修好了", 1, "通过")
    db.commit()

    assert db.get(Issue, issue.id).status == "已关闭"
    assert db.get(ComplianceCheck, check.id).status == "已闭环"


def test_close_issue_with_open_sibling_keeps_check_open(db):
    """同要求下仍有未关闭 issue 时，核验保持「有缺口」不提前闭环。"""
    req = ComplianceRequirement(customer_id=1, clause="要求A")
    db.add(req)
    db.flush()
    wo = WorkOrder(no="WO-7")
    db.add(wo)
    db.flush()
    issue1 = Issue(work_order_id=wo.id, description="x", requirement_id=req.id)
    issue2 = Issue(work_order_id=wo.id, description="y", requirement_id=req.id)
    db.add_all([issue1, issue2])
    db.flush()
    check = ComplianceCheck(requirement_id=req.id, status="有缺口", issue_id=issue1.id)
    db.add(check)
    db.flush()
    rect = Rectification(issue_id=issue1.id, plan="p")
    db.add(rect)
    db.commit()

    submit_round(db, rect.id, "修好了", 1, "通过")
    db.commit()

    # issue1 关闭，但 issue2 仍未关闭 → 核验保持有缺口
    assert db.get(Issue, issue1.id).status == "已关闭"
    assert db.get(ComplianceCheck, check.id).status == "有缺口"


def test_compute_metrics(db):
    c, ct = _mk_customer_contract(db)
    r1 = ComplianceRequirement(customer_id=c.id, project_id=ct.id, clause="A", category="技术")
    r2 = ComplianceRequirement(customer_id=c.id, project_id=ct.id, clause="B", category="组织")
    db.add_all([r1, r2])
    db.commit()
    db.add(ComplianceEvidence(requirement_id=r1.id, source_type="人工"))
    db.add(ComplianceCheck(requirement_id=r1.id, status="已核验"))
    db.commit()

    m = compute_metrics(db, customer_id=c.id)

    assert m["total"] == 2
    assert m["covered"] == 1
    assert m["verified"] == 1
    assert m["at_risk"] == 1  # r2 从未核验 = 未覆盖
    assert m["coverage_rate"] == 0.5
    assert m["closure_rate"] == 0.5
    assert m["by_category"][0]["category"] in ("技术", "组织")


def test_compute_metrics_empty(db):
    m = compute_metrics(db, customer_id=1)
    assert m["total"] == 0
    assert m["coverage_rate"] == 0.0
    assert m["by_category"] == []


def test_build_report_snapshot(db):
    c, ct = _mk_customer_contract(db)
    r = ComplianceRequirement(customer_id=c.id, project_id=ct.id, clause="A", category="技术")
    db.add(r)
    db.commit()
    db.add(ComplianceEvidence(requirement_id=r.id, source_type="人工"))
    db.commit()

    snap = build_report_snapshot(db, customer_id=c.id)

    assert snap["metrics"]["total"] == 1
    assert len(snap["requirements"]) == 1
    assert snap["requirements"][0]["evidence_count"] == 1
    assert snap["requirements"][0]["check_status"] == "未覆盖"
    assert len(snap["evidence"]) == 1
    assert snap["period"] == {"start": None, "end": None}


def test_evidence_hash_chain(db):
    """P4：每条证据链式链接，prev_hash 指向上一条 chain_hash。"""
    req = ComplianceRequirement(customer_id=1, clause="要求A")
    db.add(req)
    db.commit()
    e1 = collect(db, requirement_id=req.id, source_type="人工", content_hash="h1")
    db.commit()
    e2 = collect(db, requirement_id=req.id, source_type="人工", content_hash="h2")
    db.commit()

    assert e1.prev_hash is None
    assert e1.chain_hash is not None
    assert e2.prev_hash == e1.chain_hash
    assert e2.chain_hash != e1.chain_hash


def test_verify_chain_intact(db):
    req = ComplianceRequirement(customer_id=1, clause="要求A")
    db.add(req)
    db.commit()
    collect(db, requirement_id=req.id, source_type="人工", content_hash="h1")
    collect(db, requirement_id=req.id, source_type="人工", content_hash="h2")
    db.commit()

    result = verify_chain(db, req.id)
    assert result["intact"] is True
    assert result["total"] == 2
    assert result["broken_ids"] == []


def test_verify_chain_detects_tamper(db):
    req = ComplianceRequirement(customer_id=1, clause="要求A")
    db.add(req)
    db.commit()
    collect(db, requirement_id=req.id, source_type="人工", content_hash="h1")
    collect(db, requirement_id=req.id, source_type="人工", content_hash="h2")
    db.commit()

    first = db.query(ComplianceEvidence).order_by(ComplianceEvidence.id.asc()).first()
    first.content_hash = "TAMPERED"
    db.commit()

    result = verify_chain(db, req.id)
    assert result["intact"] is False
    assert first.id in result["broken_ids"]


def test_seed_templates(db):
    """监管要求模板库：内置四大标准模板，seed 幂等。"""
    n = seed_templates(db)
    db.commit()
    assert n == len(TEMPLATES)
    assert db.query(ComplianceRequirementTemplate).count() == len(TEMPLATES)
    # 重复 seed 不新增
    assert seed_templates(db) == 0
    # 覆盖四大标准
    sources = {s for (s,) in db.query(ComplianceRequirementTemplate.reg_source).distinct().all()}
    assert sources == {"等保2.0", "密码测评", "数据安全", "公安部176号令", "关基保护"}
