# -*- coding: utf-8 -*-
"""CCMS 常量定义 — 枚举、角色定义、限制值"""

from enum import Enum


class AgentStatus(str, Enum):
    """Agent 运行状态"""
    IDLE = "idle"           # 空闲
    WORKING = "working"     # 工作中
    RESTING = "resting"     # 休息中
    WANDERING = "wandering" # 游荡
    PRESENTING = "presenting"  # 演示/讲解
    PAUSED = "paused"       # 已暂停
    ERROR = "error"         # 异常
    OFFLINE = "offline"     # 离线


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProjectStatus(str, Enum):
    """项目状态"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    PAUSED = "paused"


class NodeStatus(str, Enum):
    """节点状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


class AgentRoleCategory(str, Enum):
    """Agent 角色类别"""
    MANAGEMENT = "management"   # 管理
    DEVELOPMENT = "development" # 开发
    SECURITY = "security"       # 安全
    FINANCE = "finance"         # 财务
    ADMIN = "admin"             # 行政


class Severity(str, Enum):
    """事件严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ── 16 个内置角色预设定义 ──
AGENT_ROLE_PRESETS = [
    {
        "role_key": "project_manager",
        "display_name": "项目经理",
        "category": AgentRoleCategory.MANAGEMENT.value,
        "icon_name": "clipboard",
        "sort_order": 1,
    },
    {
        "role_key": "architecture_designer",
        "display_name": "架构设计师",
        "category": AgentRoleCategory.DEVELOPMENT.value,
        "icon_name": "blueprint",
        "sort_order": 2,
    },
    {
        "role_key": "solution_designer",
        "display_name": "方案设计师",
        "category": AgentRoleCategory.DEVELOPMENT.value,
        "icon_name": "document",
        "sort_order": 3,
    },
    {
        "role_key": "ui_designer",
        "display_name": "UI设计师",
        "category": AgentRoleCategory.DEVELOPMENT.value,
        "icon_name": "palette",
        "sort_order": 4,
    },
    {
        "role_key": "programmer",
        "display_name": "程序员",
        "category": AgentRoleCategory.DEVELOPMENT.value,
        "icon_name": "code",
        "sort_order": 5,
    },
    {
        "role_key": "code_reviewer",
        "display_name": "代码审查员",
        "category": AgentRoleCategory.DEVELOPMENT.value,
        "icon_name": "search",
        "sort_order": 6,
    },
    {
        "role_key": "function_verifier",
        "display_name": "功能验证员",
        "category": AgentRoleCategory.DEVELOPMENT.value,
        "icon_name": "check-circle",
        "sort_order": 7,
    },
    {
        "role_key": "project_auditor",
        "display_name": "项目审计师",
        "category": AgentRoleCategory.MANAGEMENT.value,
        "icon_name": "audit",
        "sort_order": 8,
    },
    {
        "role_key": "budget_manager",
        "display_name": "预算管理员",
        "category": AgentRoleCategory.FINANCE.value,
        "icon_name": "dollar",
        "sort_order": 9,
    },
    {
        "role_key": "security_engineer",
        "display_name": "安全工程师",
        "category": AgentRoleCategory.SECURITY.value,
        "icon_name": "shield",
        "sort_order": 10,
    },
    {
        "role_key": "penetration_test_engineer",
        "display_name": "渗透测试工程师",
        "category": AgentRoleCategory.SECURITY.value,
        "icon_name": "target",
        "sort_order": 11,
    },
    {
        "role_key": "code_audit_engineer",
        "display_name": "代码审计工程师",
        "category": AgentRoleCategory.SECURITY.value,
        "icon_name": "file-search",
        "sort_order": 12,
    },
    {
        "role_key": "financial_accountant",
        "display_name": "财务会计师",
        "category": AgentRoleCategory.FINANCE.value,
        "icon_name": "calculator",
        "sort_order": 13,
    },
    {
        "role_key": "business_assistant",
        "display_name": "业务助理",
        "category": AgentRoleCategory.ADMIN.value,
        "icon_name": "briefcase",
        "sort_order": 14,
    },
    {
        "role_key": "archive_manager",
        "display_name": "档案管理员",
        "category": AgentRoleCategory.ADMIN.value,
        "icon_name": "archive",
        "sort_order": 15,
    },
    {
        "role_key": "clerk",
        "display_name": "文员",
        "category": AgentRoleCategory.ADMIN.value,
        "icon_name": "file-text",
        "sort_order": 16,
    },
]
