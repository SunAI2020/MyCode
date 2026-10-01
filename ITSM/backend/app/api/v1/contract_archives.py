"""合同原件档案：上传→抽取→加密存档→确认导入（自动生成 客户→合同→服务对象→服务项目）。"""
import hashlib
import json
import os
import uuid
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import (
    customer_scope_of,
    get_current_user,
    get_db,
    require_permission,
)
from app.models import Contract, ContractArchive, ContractItem, CmdbCi, Customer, SysUser
from app.schemas.contract import ContractOut
from app.schemas.contract_archive import ContractArchiveConfirm, ContractArchiveOut
from app.services.archive_crypto import decrypt_bytes, encrypt_bytes
from app.services.audit_service import record
from app.services.contract_extract_service import (
    extract_contract_fields,
    extract_text,
    parse_period,
)
from app.utils.pagination import paginate
from app.utils.response import ok

router = APIRouter(prefix="/contract-archives", tags=["合同原件档案"])

# 仅这些可信 MIME 允许内联渲染，其余（含历史异常数据）强制下载；图片为安全位图/光栅格式，可内联
ALLOWED_INLINE_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/png",
}

# 允许上传的扩展名 → 派生 MIME（不信任客户端 content_type，防伪造 MIME 引发存储型 XSS）
MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def _archive_dir() -> str:
    return os.path.join(settings.UPLOAD_DIR, "contracts")


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s.strip())
    except ValueError:
        return None


def _resolve_customer(db: Session, body: ContractArchiveConfirm, scope: int | None) -> Customer:
    """解析客户：显式 customer_id > 按名称精确匹配 > 新建（仅平台侧可新建）。"""
    if body.customer_id is not None:
        c = db.get(Customer, body.customer_id)
        if c is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选客户不存在")
        if scope is not None and c.id != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为该客户创建合同")
        return c
    name = (body.customer_name or "").strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "客户名称不能为空")
    existing = db.query(Customer).filter(Customer.name == name).first()
    if existing:
        if scope is not None and existing.id != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为该客户创建合同")
        return existing
    if scope is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权新建其他客户")
    c = Customer(name=name, level="普通")
    db.add(c)
    db.flush()
    return c


@router.post("/upload")
def upload_archive(
    file: UploadFile,
    user: SysUser = Depends(require_permission("contract:write")),
    db: Session = Depends(get_db),
):
    """上传原件 → 抽文本 → LLM 抽取 → 加密写盘 → 建待确认档案行。"""
    filename = (file.filename or "").strip()
    lower = filename.lower()
    if lower.endswith(".doc"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "旧版 .doc 不支持，请另存为 .docx 后重试")
    ext = os.path.splitext(lower)[1]
    if ext not in MIME_BY_EXT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持 PDF / Word(.docx) / 图片(jpg/png) 文件")
    data = file.file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件为空")
    max_bytes = settings.ARCHIVE_MAX_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"文件不能超过 {settings.ARCHIVE_MAX_MB}MB")

    # 仅依据已校验扩展名派生 MIME，不信任客户端 content_type（防伪造 MIME 引发存储型 XSS）
    mime = MIME_BY_EXT[ext]
    try:
        text, mineru_expired = extract_text(filename, data)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    extracted = extract_contract_fields(text)

    os.makedirs(_archive_dir(), exist_ok=True, mode=0o700)
    stored_name = f"{uuid.uuid4().hex}.enc"
    fd = os.open(os.path.join(_archive_dir(), stored_name), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(encrypt_bytes(data))

    obj = ContractArchive(
        original_filename=filename,
        stored_name=stored_name,
        file_hash=hashlib.sha256(data).hexdigest(),
        file_size=len(data),
        mime_type=mime,
        extracted=json.dumps(extracted, ensure_ascii=False),
        status="待确认",
        created_by=user.id,
    )
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="upload_contract_archive", resource=f"contract_archive:{obj.id}", after=filename)
    db.commit()

    return ok({
        "archive_id": obj.id,
        "extracted": extracted,
        "original_filename": filename,
        "file_size": len(data),
        "has_text": bool(text.strip()),
        # MinerU token 无效/过期（90 天）时置位，前端提示重新获取
        "mineru_expired": mineru_expired,
        # 未用 LLM 时把纯文本回传，供前端展示辅助人工补录
        "text_preview": (text[:2000] if not extracted.get("llm_used") else None),
    })


@router.post("/{aid}/confirm")
def confirm_archive(
    aid: int,
    body: ContractArchiveConfirm,
    user: SysUser = Depends(require_permission("contract:write")),
    db: Session = Depends(get_db),
):
    """按编辑后的抽取字段自动生成全链路，并把档案归档到该合同。"""
    obj = db.get(ContractArchive, aid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "档案不存在")
    if obj.status != "待确认":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该档案已确认，不可重复导入")
    scope = customer_scope_of(user, db)
    # 客户侧角色（多角色边界）只能确认「本人上传」或「已绑定本客户」的档案，防跨租户认领
    if scope is not None:
        if obj.customer_id is not None and obj.customer_id != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权确认该档案")
        if obj.customer_id is None and obj.created_by != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权确认他人上传的档案")

    # 挂到已有项目：仅归档原件，不重复生成 客户/服务对象/服务项目
    if body.contract_id is not None:
        contract = db.get(Contract, body.contract_id)
        if contract is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选项目不存在")
        if scope is not None and contract.customer_id != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该项目")
        obj.contract_id = contract.id
        obj.customer_id = contract.customer_id
        obj.status = "已确认"
        obj.extracted = json.dumps(body.model_dump(), ensure_ascii=False, default=str)
        db.flush()
        record(db, user_id=user.id, action="confirm_contract_archive", resource=f"contract_archive:{aid}", after=f"attach_to_contract:{contract.id}")
        db.commit()
        return ok(ContractOut.model_validate(contract).model_dump())

    customer = _resolve_customer(db, body, scope)

    start, end = parse_period(body.service_period)
    contract_status = "已到期" if (end is not None and end < date.today()) else "执行中"
    contract = Contract(
        customer_id=customer.id,
        type="安全服务",
        name=body.name or f"{customer.name}服务合同",
        no=body.contract_no,
        amount=body.amount,
        sign_date=_parse_date(body.sign_date),
        start_date=start,
        end_date=end,
        has_onsite=bool(body.has_onsite),
        staff_requirement=body.staff_requirement,
        accept_standard=body.accept_standard,
        delivery_docs=body.delivery_docs,
        acceptance_report_format=body.acceptance_report_format,
        service_location=body.service_location,
        status=contract_status,
    )
    db.add(contract)
    db.flush()

    # 服务对象
    ci_by_name: dict[str, CmdbCi] = {}
    for name in body.service_objects:
        name = (name or "").strip()
        if not name:
            continue
        ci = CmdbCi(customer_id=customer.id, contract_id=contract.id, name=name, type="业务系统")
        db.add(ci)
        db.flush()
        ci_by_name[name] = ci

    # 服务项目（无服务对象时兜底建默认服务对象）
    default_ci = next(iter(ci_by_name.values()), None)
    if body.service_items and default_ci is None:
        default_ci = CmdbCi(customer_id=customer.id, contract_id=contract.id, name="默认服务对象", type="业务系统")
        db.add(default_ci)
        db.flush()
        ci_by_name[default_ci.name] = default_ci

    for it in body.service_items:
        ci = ci_by_name.get(it.service_object) if it.service_object else None
        ci = ci or default_ci
        if ci is None:
            continue
        db.add(ContractItem(
            contract_id=contract.id,
            ci_id=ci.id,
            project=it.project,
            frequency=it.frequency,
            unit=it.unit,
            price=it.price,
        ))

    obj.contract_id = contract.id
    obj.customer_id = customer.id
    obj.status = "已确认"
    obj.extracted = json.dumps(body.model_dump(), ensure_ascii=False, default=str)

    db.flush()
    record(db, user_id=user.id, action="confirm_contract_archive", resource=f"contract_archive:{aid}", after=f"contract:{contract.id}")
    db.commit()
    return ok(ContractOut.model_validate(contract).model_dump())


@router.get("")
def list_archives(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    contract_id: int | None = Query(None),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """档案列表（客户侧仅见本客户已确认档案；可按合同过滤）。"""
    scope = customer_scope_of(user, db)
    q = db.query(ContractArchive).order_by(ContractArchive.id.desc())
    if scope is not None:
        q = q.filter(ContractArchive.customer_id == scope)
    if contract_id is not None:
        q = q.filter(ContractArchive.contract_id == contract_id)
    return ok(paginate(q, page, size, ContractArchiveOut))


@router.get("/{aid}/download")
def download_archive(aid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """解密下载原件。"""
    obj = db.get(ContractArchive, aid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "档案不存在")
    scope = customer_scope_of(user, db)
    if scope is not None and obj.customer_id != scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "档案不存在或无权访问")
    path = os.path.join(_archive_dir(), obj.stored_name)
    if not os.path.exists(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "原件文件缺失")
    with open(path, "rb") as f:
        token = f.read()
    data = decrypt_bytes(token)
    mime = obj.mime_type if obj.mime_type in ALLOWED_INLINE_MIME else "application/octet-stream"
    disposition = "inline" if mime != "application/octet-stream" else "attachment"
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(obj.original_filename)}",
            "X-Content-Type-Options": "nosniff",
        },
    )
