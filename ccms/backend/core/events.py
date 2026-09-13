# -*- coding: utf-8 -*-
"""CCMS 事件总线 — Redis pub/sub 封装，解耦服务间通信"""

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .redis import publish


class EventType(str, Enum):
    """事件类型枚举"""

    # Agent 事件
    AGENT_STATUS_CHANGE = "agent:status_change"
    AGENT_TASK_START = "agent:task_start"
    AGENT_TASK_PROGRESS = "agent:task_progress"
    AGENT_TASK_COMPLETE = "agent:task_complete"
    AGENT_TASK_ERROR = "agent:task_error"
    AGENT_TOKEN_USAGE = "agent:token_usage"
    AGENT_CHARACTER_ACTION = "agent:character_action"

    # 系统事件
    METRICS_UPDATE = "metrics:update"
    TERMINAL_OUTPUT = "terminal:output"
    TERMINAL_CLOSED = "terminal:closed"
    NODE_STATUS_CHANGE = "node:status_change"
    SYSTEM_EVENT = "system:event"

    # 通知事件
    NOTIFICATION_SEND = "notification:send"


def create_event(event_type: EventType, payload: dict[str, Any]) -> dict:
    """创建标准事件结构"""
    return {
        "type": event_type.value,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def emit_event(event_type: EventType, payload: dict[str, Any]) -> int:
    """发送事件到 Redis pub/sub"""
    event = create_event(event_type, payload)
    channel = event_type.value.split(":")[0]  # 使用事件前缀作为频道
    message = json.dumps(event, ensure_ascii=False)
    return await publish(channel, message)


async def emit_agent_status_change(agent_id: str, old_status: str, new_status: str) -> None:
    """快捷方法：发送 Agent 状态变更事件"""
    await emit_event(
        EventType.AGENT_STATUS_CHANGE,
        {"agent_id": agent_id, "old_status": old_status, "new_status": new_status},
    )


async def emit_agent_task_progress(
    agent_id: str, task_id: str, progress: float
) -> None:
    """快捷方法：发送 Agent 任务进度事件"""
    await emit_event(
        EventType.AGENT_TASK_PROGRESS,
        {"agent_id": agent_id, "task_id": task_id, "progress": progress},
    )


async def emit_metrics_update(metrics: dict[str, Any]) -> None:
    """快捷方法：发送系统指标更新事件"""
    await emit_event(EventType.METRICS_UPDATE, metrics)


async def emit_system_event(
    event_type_str: str,
    severity: str,
    message: str,
    source: str = "",
    data: dict | None = None,
) -> None:
    """快捷方法：发送系统事件"""
    await emit_event(
        EventType.SYSTEM_EVENT,
        {
            "event_type": event_type_str,
            "severity": severity,
            "message": message,
            "source": source,
            "data": data or {},
        },
    )
