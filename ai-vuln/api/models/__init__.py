# -*- coding: utf-8 -*-
"""Pydantic 共享模型"""
import re
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator, model_validator


def _validate_http_url(v):
    """仅允许 http/https 协议，防 javascript: 等危险 scheme（Stored XSS 防御）"""
    if v is not None and not re.match(r'^https?://', str(v), re.IGNORECASE):
        raise ValueError('url 仅支持 http/https 协议')
    return v


def _validate_ssrf_safe(v, info):
    """协议校验 + SSRF 内网阻断。

    Web 扫描 / HTTP 探测会把目标地址交给 requests 发起真实请求，
    若不阻断私网/环回/链路本地/云元数据，授权用户就能把扫描器当 SSRF 代理。
    默认拒绝内网；确需扫描内网时显式传 allow_internal=True。
    """
    v = _validate_http_url(v)
    from ssrf_guard import ssrf_guard
    # 内网放行与否是服务端决策，绝不读请求体 —— 否则客户端传个 allow_internal=true
    # 就绕过了 SSRF 防护。确需扫描内网时，应由角色/能力在路由层单独放行。
    try:
        return ssrf_guard(v, allow_internal=False)
    except ValueError as e:
        raise ValueError(f'目标地址被 SSRF 防护拒绝：{e}')

class PaginatedResponse(BaseModel):
    total: int; page: int; page_size: int; items: List[Any]

class APIResponse(BaseModel):
    success: bool = True; data: Optional[Any] = None; message: str = 'ok'

class AssetCreate(BaseModel):
    name: str = Field(..., min_length=1); ip: str
    url: Optional[str] = None
    mac: Optional[str] = None; type: str = 'SERVER'; os: Optional[str] = None
    status: str = 'ACTIVE'; tags: Optional[str] = None
    owner: Optional[str] = None; department: Optional[str] = None
    location: Optional[str] = None; importance: str = 'MEDIUM'

    _check_url = field_validator('url')(_validate_http_url)

class AssetUpdate(BaseModel):
    name: Optional[str] = None; ip: Optional[str] = None
    url: Optional[str] = None
    mac: Optional[str] = None; type: Optional[str] = None
    os: Optional[str] = None; status: Optional[str] = None
    tags: Optional[str] = None; owner: Optional[str] = None
    department: Optional[str] = None; location: Optional[str] = None
    importance: Optional[str] = None

    _check_url = field_validator('url')(_validate_http_url)

class AssetImportRequest(BaseModel):
    format: str = 'csv'  # 'csv' | 'excel'
    data: str = Field(..., min_length=1)  # CSV 文本，或 base64 编码的 Excel 字节
    tags: Optional[str] = None  # 全局附加标签

class ScanTaskCreate(BaseModel):
    target: str; scan_type: str = 'quick'
    ports: Optional[str] = None; config: Optional[dict] = None

class CVESearchParams(BaseModel):
    keyword: Optional[str] = None
    min_cvss: float = Field(default=0, ge=0, le=10)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


# ---- P1 用户 + RBAC ----
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6)
    role: str = 'viewer'
    email: Optional[str] = None
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    role: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    active: Optional[int] = None
    must_change_password: Optional[int] = None


class PasswordChange(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


# ---- P1 改进1：Web 扫描 ----
class WebScanRequest(BaseModel):
    target_url: str = Field(..., min_length=1)
    do_directory: bool = True
    do_zap: bool = True
    do_active: bool = True
    ai_enabled: bool = False

    @model_validator(mode='after')
    def _guard_ssrf(self):
        _validate_ssrf_safe(self.target_url, self)
        return self


class HTTPProbeRequest(BaseModel):
    target_url: str = Field(..., min_length=1)
    method: str = 'GET'
    path: str = '/'
    headers: Optional[dict] = None
    body: Optional[str] = None

    @model_validator(mode='after')
    def _guard_ssrf(self):
        _validate_ssrf_safe(self.target_url, self)
        return self


# ---- P1 弱口令 ----
class WeakPassRequest(BaseModel):
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    protocol: str = Field(..., min_length=1)
    credentials: Optional[List[dict]] = None


# ---- P1 漏洞处置工作流 ----
class DispositionCreate(BaseModel):
    vuln_ref: str = Field(..., min_length=1)
    vuln_title: Optional[str] = None
    severity: str = 'INFO'
    assignee: Optional[str] = None
    source: str = 'scan'


class WorkflowTransition(BaseModel):
    to_status: str = Field(..., min_length=1)
    assignee: Optional[str] = None
    note: Optional[str] = None
    reopen_reason: Optional[str] = None


# ---- 合规检查（等保 / 关基 / 数据安全） ----
class ComplianceCheckRequest(BaseModel):
    standard: str = Field(..., min_length=1)          # dengbao / cii / data_security
    level: str = 'ALL'                                # 等保 L2/L3，其它标准用 ALL
    business_system: str = ''                         # 空则落在 DEFAULT 作用域
    scan_id: Optional[int] = None                     # 复用已有扫描作为技术证据
    target: str = ''


class QuestionnaireAnswerItem(BaseModel):
    control_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)            # 符合/部分符合/不符合/不适用
    note: str = ''
    evidence_ref: str = ''


class QuestionnaireAnswerBatch(BaseModel):
    business_system: str = ''
    answered_by: str = ''
    answers: List[QuestionnaireAnswerItem] = Field(default_factory=list)
