# -*- coding: utf-8 -*-
"""文件系统浏览服务 — 安全的目录列表和磁盘枚举"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import psutil


@dataclass
class DirectoryEntry:
    """目录条目"""
    name: str
    path: str
    is_directory: bool
    size: int | None
    modified_at: str | None


def _safe_path(raw_path: str) -> str:
    """规范化路径并拒绝目录遍历攻击"""
    path = os.path.abspath(os.path.expanduser(raw_path))
    # 确保不存在 .. 遍历
    if ".." in path.split(os.sep):
        raise ValueError("路径包含非法的目录遍历")
    return path


def list_directory(path: str | None = None) -> tuple[str, list[DirectoryEntry]]:
    """列出目录内容，返回 (规范化路径, 条目列表)

    目录排在前面，按名称排序。
    """
    if path is None or path.strip() == "":
        path = os.path.expanduser("~")

    abs_path = _safe_path(path)

    if not os.path.isdir(abs_path):
        raise ValueError(f"目录不存在: {abs_path}")

    entries: list[DirectoryEntry] = []

    try:
        for name in os.listdir(abs_path):
            full = os.path.join(abs_path, name)
            try:
                stat = os.stat(full)
                entries.append(
                    DirectoryEntry(
                        name=name,
                        path=full,
                        is_directory=os.path.isdir(full),
                        size=stat.st_size if not os.path.isdir(full) else None,
                        modified_at=datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                    )
                )
            except OSError:
                # 权限不足的文件跳过
                entries.append(
                    DirectoryEntry(
                        name=name,
                        path=full,
                        is_directory=False,
                        size=None,
                        modified_at=None,
                    )
                )
    except PermissionError:
        raise ValueError(f"无权限访问目录: {abs_path}")

    # 目录优先，然后按名称排序
    entries.sort(key=lambda e: (not e.is_directory, e.name.lower()))
    return abs_path, entries


def list_drives() -> list[dict[str, Any]]:
    """列出可用磁盘分区（Windows 跨盘符支持）"""
    drives: list[dict[str, Any]] = []
    for part in psutil.disk_partitions():
        drives.append({
            "name": part.device,
            "path": part.device if os.name == "nt" else part.mountpoint,
            "mountpoint": part.mountpoint,
            "fstype": part.fstype,
        })
    return drives
