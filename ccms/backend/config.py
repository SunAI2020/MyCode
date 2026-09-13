# -*- coding: utf-8 -*-
"""CCMS 配置管理 — pydantic-settings 从环境变量加载配置"""

import json
from functools import cached_property
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，从 .env 文件和环境变量加载"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 数据库 ──
    database_url: str = "postgresql+asyncpg://ccms:ccms_secret_2026@localhost:5432/ccms"
    database_url_sync: str = "postgresql://ccms:ccms_secret_2026@localhost:5432/ccms"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── JWT ──
    jwt_secret_key: str = "ccms-dev-secret-key-change-in-production-please"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ── Anthropic API ──
    anthropic_api_key: str = ""
    anthropic_default_model: str = "claude-sonnet-4-20250514"

    # ── 微信 ──
    wechat_mini_app_id: str = ""
    wechat_mini_app_secret: str = ""
    wechat_mp_app_id: str = ""
    wechat_mp_app_secret: str = ""
    wechat_mp_token: str = ""
    wechat_mp_encoding_aes_key: str = ""

    # ── 服务 ──
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        """将逗号分隔的字符串转换为列表"""
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]
    debug: bool = True

    # ── Celery ──
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── 系统 ──
    metrics_collection_interval: int = 5  # 指标采集间隔（秒）
    agent_heartbeat_interval: int = 30  # Agent 心跳间隔（秒）
    max_agent_delegation_depth: int = 3  # Agent 委托最大深度
    command_timeout_seconds: int = 300  # 命令执行超时（秒）


# 全局单例
settings = Settings()
