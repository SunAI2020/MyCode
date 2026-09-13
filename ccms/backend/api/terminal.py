# -*- coding: utf-8 -*-
"""终端 API — 命令执行、会话管理"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import DbSession, get_current_user_id
from ..services.terminal import (
    cancel_session,
    execute_command,
    get_session,
    list_user_sessions,
)

router = APIRouter(tags=["终端"])


# ── Pydantic Schemas ──

class ExecuteRequest(BaseModel):
    """执行命令请求"""
    command: str = Field(min_length=1, max_length=4096)
    working_directory: str = Field(min_length=1, max_length=1024)


class ExecuteResponse(BaseModel):
    """执行命令响应"""
    session_id: uuid.UUID
    status: str


class SessionResponse(BaseModel):
    """终端会话响应"""
    id: uuid.UUID
    working_directory: str
    shell_type: str
    status: str
    output_buffer: str | None
    started_at: datetime
    closed_at: datetime | None

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """会话列表响应"""
    sessions: list[SessionResponse]
    total: int


# ── 端点 ──

@router.post("/sessions", response_model=ExecuteResponse, status_code=201)
async def create_session(
    req: ExecuteRequest,
    db: AsyncSession = DbSession,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """执行终端命令，创建会话"""
    try:
        session = await execute_command(
            db=db,
            user_id=user_id,
            working_directory=req.working_directory,
            command=req.command,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ExecuteResponse(
        session_id=session.id,
        status=session.status,
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    db: AsyncSession = DbSession,
    user_id: uuid.UUID = Depends(get_current_user_id),
    limit: int = 50,
):
    """获取当前用户的终端会话历史"""
    sessions = await list_user_sessions(db, user_id, limit=limit)
    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=s.id,
                working_directory=s.working_directory,
                shell_type=s.shell_type,
                status=s.status,
                output_buffer=s.output_buffer,
                started_at=s.started_at,
                closed_at=s.closed_at,
            )
            for s in sessions
        ],
        total=len(sessions),
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session_detail(
    session_id: uuid.UUID,
    db: AsyncSession = DbSession,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """获取单个终端会话详情（含输出）"""
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    return SessionResponse(
        id=session.id,
        working_directory=session.working_directory,
        shell_type=session.shell_type,
        status=session.status,
        output_buffer=session.output_buffer,
        started_at=session.started_at,
        closed_at=session.closed_at,
    )


@router.post("/sessions/{session_id}/cancel")
async def cancel_session_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = DbSession,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """取消正在运行的终端会话"""
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权操作此会话")

    try:
        await cancel_session(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "cancelled"}
