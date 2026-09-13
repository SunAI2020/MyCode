# -*- coding: utf-8 -*-
"""
CCMS — Claude Code Management System
FastAPI 主入口，包含启动/关闭生命周期管理
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .core.exceptions import CCMSException

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    from .core.redis import get_redis

    await get_redis()
    yield
    # 关闭时
    from .core.redis import close_redis

    await close_redis()


def create_app() -> FastAPI:
    """FastAPI 应用工厂"""
    app = FastAPI(
        title="CCMS - Claude Code Management System",
        description="AI 子 Agent 协同管理中控台",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS 中间件 ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── 全局异常处理 ──
    @app.exception_handler(CCMSException)
    async def ccms_exception_handler(request: Request, exc: CCMSException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "code": exc.code,
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.exception("Database error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "数据库操作失败，请稍后重试",
                "code": "DATABASE_ERROR",
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "服务器内部错误，请联系管理员",
                "code": "INTERNAL_ERROR",
            },
        )

    # ── 注册路由 ──
    from .api import router as api_router

    app.include_router(api_router, prefix="/api/v1")

    # ── 健康检查 ──
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
