"""绩效考核 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PerformanceCreate(BaseModel):
    user_id: int
    work_order_id: int
    contract_item_id: int | None = None
    workload: float = 0
    dispatch_price: float = 0
    ratio: float = 100
    quality_score: float = 1.0
    customer_score: float = 1.0


class PerformanceUpdate(BaseModel):
    workload: float | None = None
    dispatch_price: float | None = None
    ratio: float | None = None
    quality_score: float | None = None
    customer_score: float | None = None


class PerformanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    work_order_id: int
    contract_item_id: int | None = None
    workload: float
    dispatch_price: float
    ratio: float
    quality_score: float
    customer_score: float
    perf_score: float
    created_at: datetime | None = None
    # 富化字段（列表接口填充）
    user_name: str | None = None
    work_order_no: str | None = None
