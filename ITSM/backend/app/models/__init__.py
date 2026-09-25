# 汇总导入所有模型，供 Alembic autogenerate 发现
from app.models.customer import Customer
from app.models.contract import CmdbCi, Contract, ContractItem
from app.models.delivery import Delivery
from app.models.dispatch import OrderDispatch
from app.models.issue import Issue, Rectification, RectificationRecord
from app.models.onsite import OnsiteDailyReport, OnsiteService
from app.models.outsourcing import Outsourcing, OutsourcingReport, OutsourceUser
from app.models.performance import Performance
from app.models.service import ServiceCycle, ServiceReminder, SlaPolicy
from app.models.system import (
    SysAuditLog,
    SysDict,
    SysPermission,
    SysRole,
    SysRolePermission,
    SysUser,
    SysUserRole,
)
from app.models.work_order import OrderReceive, WorkOrder, WorkOrderAssignee

__all__ = [
    "SysUser",
    "SysRole",
    "SysPermission",
    "SysUserRole",
    "SysRolePermission",
    "SysAuditLog",
    "SysDict",
    "Customer",
    "Contract",
    "CmdbCi",
    "ContractItem",
    "OrderReceive",
    "OrderDispatch",
    "WorkOrder",
    "WorkOrderAssignee",
    "Issue",
    "Rectification",
    "RectificationRecord",
    "Delivery",
    "Performance",
    "OnsiteService",
    "OnsiteDailyReport",
    "OutsourceUser",
    "Outsourcing",
    "OutsourcingReport",
    "ServiceCycle",
    "ServiceReminder",
    "SlaPolicy",
]
