#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI漏洞扫描系统 Pro — REST API Server
启动: python api_server.py
文档: http://127.0.0.1:8000/api/docs
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from api.server import create_app

app = create_app()

if __name__ == '__main__':
    import uvicorn
    print(f'API 服务器: http://{config.API_HOST}:{config.API_PORT}')
    print(f'Swagger UI: http://{config.API_HOST}:{config.API_PORT}/api/docs')
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT, log_level='info')
