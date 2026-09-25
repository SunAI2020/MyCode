import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 必填（来自 .env / 环境变量），不留含密码的硬编码默认
    DATABASE_URL: str
    # 未显式配置时生成随机密钥（每次启动变化）；生产必须通过 .env 固定强随机值
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    CORS_ORIGINS: str = "http://localhost:5173"
    ENABLE_SCHEDULER: bool = False
    # 可选中间件（空 = 禁用，未配置时自动降级到进程内缓存 / SQL 检索）
    REDIS_URL: str = ""
    ELASTICSEARCH_URL: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
