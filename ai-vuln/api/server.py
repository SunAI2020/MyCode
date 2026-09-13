# -*- coding: utf-8 -*-
"""FastAPI 应用工厂 + 生命周期"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from api.dependencies import get_db_instance, release_db_instance
from api.routers import (assets, scans, cve, intel, audit, reports, dashboard,
                         auth, users, webscan, weakpass, workflow, compliance)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 前端生产构建产物（npm run build 输出）；未构建时优雅跳过托管
FRONTEND_DIR = os.path.join(_BASE_DIR, 'frontend', 'dist')


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db_instance()
    yield
    release_db_instance()


def create_app() -> FastAPI:
    app = FastAPI(
        title='AI Vulnerability Scanner API',
        version='2.1.0',
        description='AI漏洞扫描系统 Pro — RESTful API',
        docs_url='/api/docs',
        openapi_url='/api/openapi.json',
        lifespan=lifespan,
    )
    # 前端使用 Bearer token（非 cookie），无需 allow_credentials；避免 '*' + credentials 组合
    app.add_middleware(CORSMiddleware, allow_origins=['*'],
                       allow_credentials=False, allow_methods=['*'],
                       allow_headers=['*'])
    app.include_router(assets.router, prefix='/api/v1', tags=['Assets'])
    app.include_router(scans.router, prefix='/api/v1', tags=['Scans'])
    app.include_router(cve.router, prefix='/api/v1', tags=['CVE'])
    app.include_router(intel.router, prefix='/api/v1', tags=['Threat Intel'])
    app.include_router(audit.router, prefix='/api/v1', tags=['Audit'])
    app.include_router(reports.router, prefix='/api/v1', tags=['Reports'])
    app.include_router(dashboard.router, prefix='/api/v1', tags=['Dashboard'])
    app.include_router(compliance.router, prefix='/api/v1', tags=['Compliance'])
    # P1 新增路由
    app.include_router(auth.router, prefix='/api/v1', tags=['Auth'])
    app.include_router(users.router, prefix='/api/v1', tags=['Users'])
    app.include_router(webscan.router, prefix='/api/v1', tags=['Web Scan'])
    app.include_router(weakpass.router, prefix='/api/v1', tags=['Weak Password'])
    app.include_router(workflow.router, prefix='/api/v1', tags=['Workflow'])

    @app.get('/api/health')
    async def health():
        return {'status': 'ok', 'version': '2.1.0'}

    # 托管 React 前端（多用户访问，本地静态资源，无 CDN）
    if os.path.isdir(FRONTEND_DIR):
        from fastapi.staticfiles import StaticFiles
        app.mount('/', StaticFiles(directory=FRONTEND_DIR, html=True), name='frontend')
    return app
