"""报告台账 CRUD + 服务报告文件（脱敏 + 加密入库）。"""
import hashlib
import html as html_mod
import json
import os
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import assert_scoped, customer_scope_of, get_db, require_role, scope_filter
from app.core.security import mask_text
from app.models import Contract, Customer, Report, SysUser, WorkOrder
from app.schemas.report import ReportCreate, ReportOut, ReportUpdate
from app.services.archive_crypto import decrypt_bytes, encrypt_bytes
from app.services.audit_service import record
from app.services.contract_extract_service import extract_text
from app.utils.response import ok

ROLE = ("sys_admin", "sys_ops", "ticket_mgr")
READ_ROLE = ("sys_admin", "sys_ops", "ticket_mgr", "cust_admin", "cust_service")

router = APIRouter(prefix="/reports", tags=["报告中心"])

# 允许上传的扩展名 → 派生 MIME（不信任客户端 content_type）
REPORT_MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

# 仅可信二进制/位图可内联渲染；md/html 强制下载（防存储型 XSS）
ALLOWED_INLINE_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/png",
}


def _html_to_text(s: str) -> str:
    return html_mod.unescape(re.sub(r"<[^>]+>", " ", s))


def _extract_report_text(filename: str, data: bytes) -> str:
    """按扩展名抽取报告纯文本：md/html 直接解码，pdf/docx/图片复用合同抽取。"""
    lower = (filename or "").lower()
    if lower.endswith((".md", ".html", ".htm")):
        for enc in ("utf-8", "utf-8-sig", "gbk"):
            try:
                text = data.decode(enc)
                return _html_to_text(text) if lower.endswith((".html", ".htm")) else text
            except UnicodeDecodeError:
                continue
        return ""
    try:
        text, _ = extract_text(filename, data)
        return text
    except ValueError:
        return ""


def _enrich(db: Session, items: list[dict]) -> None:
    cids = {it["customer_id"] for it in items if it["customer_id"]}
    pids = {it["contract_id"] for it in items if it["contract_id"]}
    wids = {it["work_order_id"] for it in items if it["work_order_id"]}
    cname = {c.id: c.name for c in db.query(Customer).filter(Customer.id.in_(cids)).all()} if cids else {}
    pname = {c.id: c.name for c in db.query(Contract).filter(Contract.id.in_(pids)).all()} if pids else {}
    wno = {w.id: w.no for w in db.query(WorkOrder).filter(WorkOrder.id.in_(wids)).all()} if wids else {}
    for it in items:
        it["customer_name"] = cname.get(it["customer_id"])
        it["project_name"] = pname.get(it["contract_id"])
        it["work_order_no"] = wno.get(it["work_order_id"])


@router.get("")
def list_reports(
    report_type: str | None = Query(None),
    status: str | None = Query(None),
    work_order_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*READ_ROLE)),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    q = scope_filter(db.query(Report), Report, scope)
    if report_type:
        q = q.filter(Report.report_type == report_type)
    if status:
        q = q.filter(Report.status == status)
    if work_order_id is not None:
        q = q.filter(Report.work_order_id == work_order_id)
    total = q.count()
    rows = q.order_by(Report.id.desc()).offset((page - 1) * size).limit(size).all()
    items = []
    for r in rows:
        d = ReportOut.model_validate(r).model_dump()
        d["has_file"] = r.content_enc is not None
        items.append(d)
    data = {"items": items, "total": total, "page": page, "size": size}
    _enrich(db, data["items"])
    return ok(data)


@router.post("/upload")
def upload_report(
    file: UploadFile = File(...),
    work_order_id: int | None = Form(None),
    report_type: str = Form("运维报告"),
    title: str | None = Form(None),
    report_data: str | None = Form(None),
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    """上传服务报告：提取文本 → 脱敏 → Fernet 加密入库，挂在工单（反推项目/客户）下。"""
    filename = (file.filename or "").strip()
    ext = os.path.splitext(filename.lower())[1]
    if ext not in REPORT_MIME_BY_EXT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持 PDF / Word(.docx) / Markdown(.md) / HTML / 图片(jpg/png) 文件")
    data = file.file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件为空")
    max_bytes = settings.ARCHIVE_MAX_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"文件不能超过 {settings.ARCHIVE_MAX_MB}MB")

    mime = REPORT_MIME_BY_EXT[ext]
    raw_text = _extract_report_text(filename, data)
    masked = mask_text(raw_text)

    contract_id = customer_id = None
    if work_order_id is not None:
        wo = db.get(WorkOrder, work_order_id)
        if wo is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
        assert_scoped(wo, customer_scope_of(user, db), db)
        contract_id = wo.contract_id
        customer_id = wo.customer_id
        if customer_id is None and contract_id is not None:
            _c = db.get(Contract, contract_id)
            customer_id = _c.customer_id if _c else None

    # 结构化报告内容同样脱敏：工作内容/详细情况含敏感信息（漏洞 IP、联系方式等），不落明文
    if report_data:
        try:
            rd = json.loads(report_data)
            if isinstance(rd, dict):
                for k in ("work_content", "details"):
                    if isinstance(rd.get(k), str):
                        rd[k] = mask_text(rd[k])
                report_data = json.dumps(rd, ensure_ascii=False)
        except (ValueError, TypeError):
            pass

    obj = Report(
        title=(title or "").strip() or os.path.splitext(filename)[0],
        report_type=report_type,
        customer_id=customer_id,
        contract_id=contract_id,
        work_order_id=work_order_id,
        status="已提交",
        summary=(masked[:500] if masked else None),
        original_filename=filename,
        mime_type=mime,
        file_size=len(data),
        file_hash=hashlib.sha256(data).hexdigest(),
        content_enc=encrypt_bytes(data),
        masked_text=masked,
        report_data=report_data,
    )
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="upload_report", resource=f"report:{obj.id}", after=filename)
    db.commit()
    return ok(ReportOut.model_validate(obj).model_dump())


@router.post("")
def create_report(
    body: ReportCreate,
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    obj = Report(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"report:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(ReportOut.model_validate(obj).model_dump())


@router.get("/{rid}/preview")
def preview_report(rid: int, user: SysUser = Depends(require_role(*READ_ROLE)), db: Session = Depends(get_db)):
    """返回报告脱敏文本，供在线预览/搜索（不泄露敏感信息）。"""
    obj = db.get(Report, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "报告不存在")
    scope = customer_scope_of(user, db)
    if scope is not None and obj.customer_id != scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "报告不存在或无权访问")
    return ok({
        "title": obj.title,
        "original_filename": obj.original_filename,
        "mime_type": obj.mime_type,
        "masked_text": obj.masked_text or "",
    })


@router.get("/{rid}/download")
def download_report(rid: int, user: SysUser = Depends(require_role(*READ_ROLE)), db: Session = Depends(get_db)):
    """解密下载报告原文。"""
    obj = db.get(Report, rid)
    if obj is None or obj.content_enc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "报告或附件不存在")
    scope = customer_scope_of(user, db)
    if scope is not None and obj.customer_id != scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "报告不存在或无权访问")
    data = decrypt_bytes(obj.content_enc)
    mime = obj.mime_type if obj.mime_type in ALLOWED_INLINE_MIME else "application/octet-stream"
    disposition = "inline" if mime != "application/octet-stream" else "attachment"
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(obj.original_filename or 'report')}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.put("/{rid}")
def update_report(
    rid: int,
    body: ReportUpdate,
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    obj = db.get(Report, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "报告不存在")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"report:{rid}", after=str(data))
    db.commit()
    return ok(ReportOut.model_validate(obj).model_dump())


@router.delete("/{rid}")
def delete_report(
    rid: int,
    user: SysUser = Depends(require_role("sys_admin", "sys_ops")),
    db: Session = Depends(get_db),
):
    obj = db.get(Report, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "报告不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"report:{rid}")
    db.commit()
    return ok({"deleted": rid})
