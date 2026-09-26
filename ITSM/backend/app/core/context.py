"""请求级上下文（ContextVar）：线程安全的客户端 IP 传递。

在 get_current_user 中捕获，audit_service.record 中读取，补全审计留痕的 IP 要素。
"""
from contextvars import ContextVar

client_ip: ContextVar[str | None] = ContextVar("client_ip", default=None)
