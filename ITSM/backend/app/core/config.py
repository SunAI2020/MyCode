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
    # 仅当后端置于可信反代（nginx）之后时置 True，才信任 X-Real-IP 取真实客户端 IP；
    # 直连暴露时保持 False，避免客户端伪造反代头
    TRUST_PROXY_HEADERS: bool = False
    # 可选中间件（空 = 禁用，未配置时自动降级到进程内缓存 / SQL 检索）
    REDIS_URL: str = ""
    ELASTICSEARCH_URL: str = ""
    # 可配置大模型（OpenAI 兼容 API；空 = 未启用，RAG 降级为纯检索）
    LLM_API_BASE: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    # 上传文件存储目录（签到拍照等），相对工作目录
    UPLOAD_DIR: str = "uploads"
    # 合同原件档案：加密密钥（Fernet base64；空=自动生成并持久化到 uploads/contracts/.archive.key）
    ARCHIVE_ENC_KEY: str = ""
    ARCHIVE_MAX_MB: int = 20
    # 提醒多渠道路由 webhook（空 = 未配置，降级站内）
    WECOM_WEBHOOK: str = ""
    FEISHU_WEBHOOK: str = ""
    DINGTALK_WEBHOOK: str = ""
    # 人脸识别登录（需接入人脸比对 SDK；False = 预留，端点返回不支持）
    FACE_VERIFY_ENABLED: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
