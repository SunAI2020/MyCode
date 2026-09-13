# -*- coding: utf-8 -*-
"""CCMS 自定义异常层次结构"""


class CCMSException(Exception):
    """CCMS 基础异常"""

    def __init__(self, message: str, status_code: int = 500, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


# ── 认证异常 ──
class AuthenticationError(CCMSException):
    """认证失败"""

    def __init__(self, message: str = "认证失败"):
        super().__init__(message, status_code=401, code="AUTHENTICATION_ERROR")


class PermissionDeniedError(CCMSException):
    """权限不足"""

    def __init__(self, message: str = "权限不足"):
        super().__init__(message, status_code=403, code="PERMISSION_DENIED")


# ── 资源异常 ──
class NotFoundError(CCMSException):
    """资源不存在"""

    def __init__(self, resource: str = "资源", identifier: str = ""):
        message = f"{resource}不存在" + (f": {identifier}" if identifier else "")
        super().__init__(message, status_code=404, code="NOT_FOUND")


class ConflictError(CCMSException):
    """资源冲突"""

    def __init__(self, message: str = "资源冲突"):
        super().__init__(message, status_code=409, code="CONFLICT")


# ── 业务异常 ──
class AgentError(CCMSException):
    """Agent 相关异常"""

    def __init__(self, message: str, code: str = "AGENT_ERROR"):
        super().__init__(message, status_code=400, code=code)


class AgentBusyError(AgentError):
    """Agent 忙碌"""

    def __init__(self, agent_name: str = ""):
        message = f"Agent「{agent_name}」正在忙碌中" if agent_name else "Agent 正在忙碌中"
        super().__init__(message, code="AGENT_BUSY")


class AgentOfflineError(AgentError):
    """Agent 离线"""

    def __init__(self, agent_name: str = ""):
        message = f"Agent「{agent_name}」当前离线" if agent_name else "Agent 当前离线"
        super().__init__(message, code="AGENT_OFFLINE")


class TaskError(CCMSException):
    """任务相关异常"""

    def __init__(self, message: str, code: str = "TASK_ERROR"):
        super().__init__(message, status_code=400, code=code)


# ── 外部服务异常 ──
class ExternalServiceError(CCMSException):
    """外部服务异常（可重试）"""

    def __init__(self, service: str, message: str = "", retryable: bool = True):
        msg = f"{service}服务异常" + (f": {message}" if message else "")
        self.retryable = retryable
        super().__init__(msg, status_code=502, code="EXTERNAL_SERVICE_ERROR")


class AnthropicAPIError(ExternalServiceError):
    """Anthropic API 异常"""

    def __init__(self, message: str = "", retryable: bool = True):
        super().__init__("Anthropic API", message, retryable)
        self.code = "ANTHROPIC_API_ERROR"


class WeChatAPIError(ExternalServiceError):
    """微信 API 异常"""

    def __init__(self, message: str = "", retryable: bool = True):
        super().__init__("微信 API", message, retryable)
        self.code = "WECHAT_API_ERROR"


# ── 验证异常 ──
class ValidationError(CCMSException):
    """数据验证异常"""

    def __init__(self, message: str):
        super().__init__(message, status_code=422, code="VALIDATION_ERROR")


class TokenBudgetExceededError(CCMSException):
    """Token 预算超限"""

    def __init__(self, current: int, limit: int):
        super().__init__(
            f"Token 预算超限：已使用 {current}/{limit}",
            status_code=429,
            code="TOKEN_BUDGET_EXCEEDED",
        )
