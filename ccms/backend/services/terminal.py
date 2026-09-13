# -*- coding: utf-8 -*-
"""终端命令执行服务 — 管理命令行进程生命周期"""

import asyncio
import os
import signal
import subprocess
import traceback
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import async_session_factory
from ..models.terminal import TerminalSession


async def execute_command(
    db: AsyncSession,
    user_id: uuid.UUID,
    working_directory: str,
    command: str,
    shell_type: str = "bash",
) -> TerminalSession:
    """执行 shell 命令，创建终端会话记录并返回"""
    # 规范化工作目录
    working_directory = os.path.abspath(os.path.expanduser(working_directory))
    if not os.path.isdir(working_directory):
        raise ValueError(f"目录不存在: {working_directory}")

    # 创建会话记录
    session = TerminalSession(
        user_id=user_id,
        working_directory=working_directory,
        shell_type=shell_type,
        status="active",
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # 后台执行命令（使用独立的数据库 session）
    session_id = session.id
    asyncio.create_task(
        _run_command(session_id, working_directory, command),
    )

    return session


async def _run_command(
    session_id: uuid.UUID,
    working_directory: str,
    command: str,
) -> None:
    """后台任务：在独立线程中执行命令并捕获输出"""
    output_text: str = ""
    returncode: int | None = None

    try:
        # 在线程池中执行 subprocess（兼容 Windows asyncio 事件循环限制）
        def _sync_run() -> tuple[str, int]:
            proc = subprocess.run(
                command,
                cwd=working_directory,
                shell=True,
                capture_output=True,
                text=True,
                timeout=settings.command_timeout_seconds,
                encoding="utf-8",
                errors="replace",
            )
            return proc.stdout, proc.returncode

        output_text, returncode = await asyncio.to_thread(_sync_run)

    except subprocess.TimeoutExpired:
        output_text = f"\n[命令超时 ({settings.command_timeout_seconds}s)，已终止]"
    except Exception as e:
        output_text = f"\n[错误: {e}]\n[Traceback: {traceback.format_exc()}]"

    # 最终写入数据库
    status = "completed" if returncode == 0 else "error"
    async with async_session_factory() as db:
        try:
            stmt = select(TerminalSession).where(TerminalSession.id == session_id)
            result = await db.execute(stmt)
            s = result.scalar_one_or_none()
            if s:
                s.output_buffer = output_text
                s.status = status
                s.closed_at = datetime.now(timezone.utc)
                await db.commit()
        except Exception:
            await db.rollback()


async def cancel_session(db: AsyncSession, session_id: uuid.UUID) -> TerminalSession | None:
    """取消正在运行的终端会话"""
    stmt = select(TerminalSession).where(TerminalSession.id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        return None

    if session.status != "active":
        raise ValueError("会话未在运行中，无法取消")

    # 尝试终止进程
    if session.pid:
        try:
            if os.name == "nt":
                os.kill(session.pid, signal.SIGTERM)
            else:
                os.killpg(session.pid, signal.SIGTERM)
        except Exception:
            pass

    session.status = "cancelled"
    session.closed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(
    db: AsyncSession, session_id: uuid.UUID
) -> TerminalSession | None:
    """获取单个终端会话"""
    stmt = select(TerminalSession).where(TerminalSession.id == session_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_user_sessions(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 50
) -> list[TerminalSession]:
    """获取用户最近的终端会话列表"""
    stmt = (
        select(TerminalSession)
        .where(TerminalSession.user_id == user_id)
        .order_by(TerminalSession.started_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
