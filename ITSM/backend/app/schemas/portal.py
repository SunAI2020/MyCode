"""自助门户 schema。"""
from pydantic import BaseModel


class PortalTicketCreate(BaseModel):
    customer_id: int | None = None  # 客户侧自动取本人 scope；平台侧必填
    contract_id: int | None = None
    contract_item_id: int | None = None
    ci_id: int | None = None
    project: str | None = None
    contact: str | None = None  # 甲方联系人/电话（脱敏）
    priority: str = "中"
    description: str
