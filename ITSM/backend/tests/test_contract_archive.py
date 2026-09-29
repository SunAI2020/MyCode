"""合同原件导入单测：加密往返 / 上传建档 / 确认后自动生成全链路 / 客户复用 / 越权拒绝。"""
import io
from datetime import date

import pytest
from fastapi import HTTPException, UploadFile

from app.api.v1.contract_archives import confirm_archive, upload_archive
from app.api.v1.contracts import create_item
from app.core.config import settings
from app.models import (
    Contract,
    ContractArchive,
    ContractItem,
    CmdbCi,
    Customer,
    SysRole,
    SysUser,
    SysUserRole,
)
from app.schemas.contract import ContractItemCreate
from app.schemas.contract_archive import ContractArchiveConfirm, ServiceItemIn
from app.services.archive_crypto import decrypt_bytes, encrypt_bytes
from app.services.contract_extract_service import extract_contract_fields


def _mk_user(db):
    u = SysUser(username="admin", name="管理员", pwd_hash="x")
    db.add(u)
    db.commit()
    return u


def _mk_archive(db, u):
    obj = ContractArchive(
        original_filename="a.pdf", stored_name="x.enc", file_hash="h",
        file_size=1, mime_type="application/pdf", status="待确认", created_by=u.id,
    )
    db.add(obj)
    db.commit()
    return obj


def test_mineru_disabled_without_token(monkeypatch):
    """未配置 MINERU_TOKEN 时不走云端、不发起网络请求，返回空串。"""
    from app.core.config import settings
    from app.services.contract_extract_service import _extract_mineru
    monkeypatch.setattr(settings, "MINERU_TOKEN", "")
    assert _extract_mineru(b"%PDF-1.4 fake", ".pdf") == ""


def test_extract_text_image_mineru_expired(monkeypatch):
    """图片 OCR 遇 MinerU token 过期 → 返回空文本 + mineru_expired=True。"""
    from app.services import contract_extract_service as ces

    def _raise(data, suffix):
        raise ces.MineruTokenExpired()

    monkeypatch.setattr(ces, "_extract_mineru", _raise)
    text, expired = ces.extract_text("合同.png", b"\x89PNG fake")
    assert text == ""
    assert expired is True


def test_extract_text_pdf_falls_back_on_expired(monkeypatch):
    """PDF 遇 token 过期仍回退本地 pypdf，并带出 expired 标志。"""
    from app.services import contract_extract_service as ces

    def _raise(data, suffix):
        raise ces.MineruTokenExpired()

    monkeypatch.setattr(ces, "_extract_mineru", _raise)
    monkeypatch.setattr(ces, "_extract_pdf_pypdf", lambda data: "回退文本")
    text, expired = ces.extract_text("合同.pdf", b"%PDF fake")
    assert text == "回退文本"
    assert expired is True


def test_rule_extract_xufang_contract():
    """需方/供方式合同：名称/需方客户/服务对象与项目/验收标准/交付文档/服务地点。"""
    text = (
        "太原市数字健康保障中心网络安全设备维保采购项目\n"
        "服务合同\n"
        "需方：太原市数字健康保障中心\n"
        "供方：山西有信网安科技有限公司\n"
        "供方向需方提供网络安全设备维保及网络安全服务（具体服务内容及服务期等见后附明细）\n"
        "二、合同总金额:\n"
        "（小写）：￥409850元\n"
        "六、交验\n"
        "1、完成响应文件中约定的全部网络安全维保服务事项。\n"
        "2、遵循响应文件中约定的技术标准。\n"
        "5、验收交付文档：(1)网络安全设备维保方案；(2)项目维保记录；\n"
        "七、需方责任\n"
        "2、服务地点：太原市万柏林区望景路5号\n"
    )
    r = extract_contract_fields(text)
    assert r["name"] == "太原市数字健康保障中心网络安全设备维保采购项目服务合同"
    assert r["customer_name"] == "太原市数字健康保障中心"
    assert r["amount"] == 409850.0
    assert r["service_location"] == "太原市万柏林区望景路5号"
    assert r["service_objects"] == ["网络安全设备"]
    assert [i["project"] for i in r["service_items"]] == ["网络安全设备维保", "网络安全服务"]
    assert "完成响应文件中约定的全部" in (r["accept_standard"] or "")
    assert r["delivery_docs"] == "(1)网络安全设备维保方案；(2)项目维保记录；"


def test_rule_extract_fallback():
    """无 LLM 时规则抽取常见字段，识别结果不空。"""
    text = (
        "安全服务合同\n"
        "合同编号：HT-2026-001\n"
        "甲方：某科技有限公司\n"
        "乙方：某安全公司\n"
        "合同金额：人民币 12万元\n"
        "服务期限：2026-01-01 至 2026-12-31\n"
        "驻场服务：是\n"
        "服务对象：OA系统、数据库服务器\n"
    )
    r = extract_contract_fields(text)
    assert r["llm_used"] is False
    assert r["contract_no"] == "HT-2026-001"
    assert r["customer_name"] == "某科技有限公司"
    assert r["amount"] == 120000.0
    assert r["has_onsite"] is True
    assert r["sign_date"] == "2026-01-01"
    assert r["service_period"] == "2026-01-01 至 2026-12-31"
    assert r["service_objects"] == ["OA系统", "数据库服务器"]


def test_encrypt_decrypt_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    raw = b"contract-original-bytes-content"
    token = encrypt_bytes(raw)
    assert token != raw
    assert decrypt_bytes(token) == raw


def test_upload_creates_encrypted_archive(tmp_path, monkeypatch, db):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "MINERU_TOKEN", "")  # 屏蔽云端，避免单测真实联网
    u = _mk_user(db)
    f = UploadFile(filename="合同A.pdf", file=io.BytesIO(b"%PDF-1.4 fake content"))
    data = upload_archive(file=f, user=u, db=db)["data"]

    obj = db.get(ContractArchive, data["archive_id"])
    assert obj.status == "待确认"
    assert obj.original_filename == "合同A.pdf"
    assert len(obj.file_hash) == 64  # SHA-256 十六进制
    assert data["extracted"]["llm_used"] is False

    path = tmp_path / "contracts" / obj.stored_name
    assert path.exists()
    on_disk = path.read_bytes()
    assert on_disk != b"%PDF-1.4 fake content"  # 落盘为密文
    assert decrypt_bytes(on_disk) == b"%PDF-1.4 fake content"


def test_upload_rejects_unsupported_type(db):
    u = _mk_user(db)
    f = UploadFile(filename="合同.doc", file=io.BytesIO(b"old word"))
    with pytest.raises(HTTPException) as exc:
        upload_archive(file=f, user=u, db=db)
    assert exc.value.status_code == 400


def test_confirm_generates_full_chain(db):
    u = _mk_user(db)
    obj = _mk_archive(db, u)
    body = ContractArchiveConfirm(
        customer_name="新客户",
        contract_no="HT-1",
        sign_date="2026-01-01",
        amount=120000,
        has_onsite=True,
        service_period="2026-01-01 至 2026-12-31",
        staff_requirement="2人",
        accept_standard="按SLA",
        delivery_docs="月报",
        acceptance_report_format="PDF",
        service_objects=["OA系统", "数据库"],
        service_items=[
            ServiceItemIn(project="漏洞扫描", frequency=1, unit="月", price=5000, service_object="OA系统"),
            ServiceItemIn(project="渗透测试", frequency=1, unit="季度", price=20000),
        ],
    )
    data = confirm_archive(obj.id, body, user=u, db=db)["data"]

    ct = db.get(Contract, data["id"])
    assert ct.no == "HT-1"
    assert ct.sign_date == date(2026, 1, 1)
    assert ct.start_date == date(2026, 1, 1)
    assert ct.end_date == date(2026, 12, 31)
    assert ct.has_onsite is True
    assert ct.staff_requirement == "2人"
    assert ct.amount == 120000

    customer = db.get(Customer, ct.customer_id)
    assert customer.name == "新客户"

    cis = db.query(CmdbCi).filter_by(contract_id=ct.id).all()
    assert {c.name for c in cis} == {"OA系统", "数据库"}
    items = db.query(ContractItem).filter_by(contract_id=ct.id).all()
    assert {i.project for i in items} == {"漏洞扫描", "渗透测试"}
    # 第二项无 service_object → 归到首个服务对象
    first_ci = next(c for c in cis if c.name == "OA系统")
    assert all(i.ci_id == first_ci.id for i in items)

    obj2 = db.get(ContractArchive, obj.id)
    assert obj2.status == "已确认"
    assert obj2.contract_id == ct.id
    assert obj2.customer_id == customer.id


def test_confirm_reuses_existing_customer(db):
    u = _mk_user(db)
    c = Customer(name="老客户")
    db.add(c)
    db.commit()
    obj = _mk_archive(db, u)
    body = ContractArchiveConfirm(customer_name="老客户", service_objects=[], service_items=[])
    data = confirm_archive(obj.id, body, user=u, db=db)["data"]
    ct = db.get(Contract, data["id"])
    assert ct.customer_id == c.id
    assert db.query(Customer).count() == 1  # 未新建客户


def test_confirm_attaches_to_existing_contract(db):
    """带 contract_id 时仅归档原件到已有项目，不重复生成客户/服务对象/服务项目。"""
    u = _mk_user(db)
    c = Customer(name="既有客户")
    db.add(c)
    db.commit()
    existing = Contract(customer_id=c.id, type="安全服务", name="既有项目", no="HT-EXIST")
    db.add(existing)
    db.commit()
    obj = _mk_archive(db, u)
    body = ContractArchiveConfirm(
        contract_id=existing.id,
        customer_name="（应被忽略）",
        service_objects=["不应创建"],
        service_items=[ServiceItemIn(project="不应创建", frequency=1, unit="月")],
    )
    data = confirm_archive(obj.id, body, user=u, db=db)["data"]

    assert data["id"] == existing.id
    assert db.query(Contract).count() == 1  # 未新建项目
    assert db.query(Customer).count() == 1  # 未新建客户
    assert db.query(CmdbCi).filter_by(contract_id=existing.id).count() == 0
    assert db.query(ContractItem).filter_by(contract_id=existing.id).count() == 0

    obj2 = db.get(ContractArchive, obj.id)
    assert obj2.status == "已确认"
    assert obj2.contract_id == existing.id
    assert obj2.customer_id == c.id


def test_confirm_rejects_foreign_archive(db):
    """客户侧角色不能确认他人上传的待确认档案（防跨租户认领）。"""
    c = Customer(name="A客户")
    db.add(c)
    db.commit()
    role = SysRole(code="ticket_mgr", name="工单管理", scope="platform")
    db.add(role)
    db.flush()
    u = SysUser(username="mgr", name="工单", pwd_hash="x")
    db.add(u)
    db.flush()
    db.add(SysUserRole(user_id=u.id, role_id=role.id, customer_id=c.id))
    db.commit()
    other = SysUser(username="other", name="他人", pwd_hash="x")
    db.add(other)
    db.commit()
    obj = ContractArchive(
        original_filename="a.pdf", stored_name="x.enc", file_hash="h",
        file_size=1, mime_type="application/pdf", status="待确认", created_by=other.id,
    )
    db.add(obj)
    db.commit()
    body = ContractArchiveConfirm(customer_name="A客户", service_objects=[], service_items=[])
    with pytest.raises(HTTPException) as exc:
        confirm_archive(obj.id, body, user=u, db=db)
    assert exc.value.status_code == 403


def test_confirm_rejects_out_of_scope(db):
    c = Customer(name="A客户")
    db.add(c)
    db.commit()
    role = SysRole(code="ticket_mgr", name="工单管理", scope="platform")
    db.add(role)
    db.flush()
    u = SysUser(username="mgr", name="工单", pwd_hash="x")
    db.add(u)
    db.flush()
    db.add(SysUserRole(user_id=u.id, role_id=role.id, customer_id=c.id))
    db.commit()
    obj = _mk_archive(db, u)
    body = ContractArchiveConfirm(customer_name="B客户", service_objects=[], service_items=[])
    with pytest.raises(HTTPException) as exc:
        confirm_archive(obj.id, body, user=u, db=db)
    assert exc.value.status_code == 403


def test_create_item_without_ci_sets_null(db):
    """服务项目不关联具体系统：ci_id 为空 + 指定项目 → 正常创建，ci_id 为 None。"""
    u = _mk_user(db)
    c = Customer(name="客户")
    db.add(c)
    db.commit()
    ct = Contract(customer_id=c.id, type="安全服务", name="项目")
    db.add(ct)
    db.commit()
    body = ContractItemCreate(ci_id=None, contract_id=ct.id, project="漏洞扫描")
    data = create_item(body, user=u, db=db)["data"]
    assert data["ci_id"] is None
    assert data["contract_id"] == ct.id
    assert data["project"] == "漏洞扫描"


def test_create_item_with_ci_derives_contract(db):
    """关联服务目标时 contract_id 由服务目标派生。"""
    u = _mk_user(db)
    c = Customer(name="客户")
    db.add(c)
    db.commit()
    ct = Contract(customer_id=c.id, type="安全服务", name="项目")
    db.add(ct)
    db.commit()
    ci = CmdbCi(customer_id=c.id, contract_id=ct.id, name="OA系统")
    db.add(ci)
    db.commit()
    body = ContractItemCreate(ci_id=ci.id, project="渗透测试")
    data = create_item(body, user=u, db=db)["data"]
    assert data["ci_id"] == ci.id
    assert data["contract_id"] == ct.id


def test_create_item_without_ci_requires_contract(db):
    """不关联系统且未指定项目 → 400。"""
    u = _mk_user(db)
    body = ContractItemCreate(ci_id=None, contract_id=None, project="漏洞扫描")
    with pytest.raises(HTTPException) as exc:
        create_item(body, user=u, db=db)
    assert exc.value.status_code == 400
