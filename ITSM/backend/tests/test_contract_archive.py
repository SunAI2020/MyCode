"""合同原件导入单测：加密往返 / 上传建档 / 确认后自动生成全链路 / 客户复用 / 越权拒绝。"""
import io
from datetime import date

import pytest
from fastapi import HTTPException, UploadFile

from app.api.v1.contract_archives import confirm_archive, upload_archive
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


def test_rule_extract_fallback():
    """无 LLM 时规则抽取常见字段，识别结果不空。"""
    text = (
        "安全服务合同\n"
        "合同编号：HT-2026-001\n"
        "甲方：某科技有限公司\n"
        "乙方：某安全公司\n"
        "合同金额：12万元\n"
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
