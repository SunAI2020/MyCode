# -*- coding: utf-8 -*-
"""文件系统 API — 目录浏览、磁盘枚举"""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import get_current_user_id
from ..services.filesystem import list_drives, list_directory

router = APIRouter(tags=["文件系统"])


# ── 端点 ──

@router.get("/list")
async def list_directory_endpoint(
    path: str = Query(default="~", description="要浏览的目录路径"),
):
    """列出指定目录的内容（目录优先排列）"""
    try:
        abs_path, entries = list_directory(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "current_path": abs_path,
        "entries": [
            {
                "name": e.name,
                "path": e.path,
                "is_directory": e.is_directory,
                "size": e.size,
                "modified_at": e.modified_at,
            }
            for e in entries
        ],
    }


@router.get("/drives")
async def list_drives_endpoint():
    """列出可用磁盘分区"""
    return {"drives": list_drives()}
