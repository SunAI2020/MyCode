"""报告台账 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReportCreate(BaseModel):
    title: str
    report_type: str = "运维报告"
    customer_id: int | None = None
    contract_id: int | None = None
    work_order_id: int | None = None
    report_no: str | None = None
    status: str = "草稿"
    summary: str | None = None


class ReportUpdate(BaseModel):
    title: str | None = None
    report_type: str | None = None
    customer_id: int | None = None
    contract_id: int | None = None
    work_order_id: int | None = None
    report_no: str | None = None
    status: str | None = None
    summary: str | None = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    report_type: str
    customer_id: int | None = None
    contract_id: int | None = None
    work_order_id: int | None = None
    report_no: str | None = None
    status: str
    summary: str | None = None
    created_at: datetime | None = None
    # 富化字段（列表接口填充）
    customer_name: str | None = None
    project_name: str | None = None
    work_order_no: str | None = None
    # 报告文件（服务报告附件）
    original_filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    has_file: bool = False
    report_data: str | None = None
