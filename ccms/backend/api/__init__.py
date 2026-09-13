# -*- coding: utf-8 -*-
"""CCMS API 路由聚合"""

from fastapi import APIRouter

from .auth import router as auth_router
from .filesystem import router as filesystem_router
from .terminal import router as terminal_router

router = APIRouter()

# ── 认证模块 ──
router.include_router(auth_router, prefix="/auth", tags=["认证"])

# ── 文件系统 ──
router.include_router(filesystem_router, prefix="/filesystem", tags=["文件系统"])

# ── 终端 ──
router.include_router(terminal_router, prefix="/terminal", tags=["终端"])

# 后续路由将在对应阶段注册:
# router.include_router(projects_router, prefix="/projects", tags=["项目"])
# router.include_router(agents_router, prefix="/agents", tags=["Agent"])
# router.include_router(files_router, prefix="/files", tags=["文件"])
# router.include_router(metrics_router, prefix="/metrics", tags=["指标"])
# router.include_router(skills_router, prefix="/skills", tags=["技能"])
# router.include_router(cron_router, prefix="/cron-jobs", tags=["定时任务"])
# router.include_router(nodes_router, prefix="/nodes", tags=["节点"])
# router.include_router(dashboard_router, prefix="/dashboard", tags=["仪表盘"])
# router.include_router(settings_router, prefix="/settings", tags=["设置"])
