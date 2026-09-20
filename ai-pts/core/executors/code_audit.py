"""
Semgrep 执行器（本地源码静态审计，目标为本地路径，非远程攻击面）。
"""
from __future__ import annotations

from typing import List, Optional

from core.executors.base import ToolExecutor


class SemgrepExecutor(ToolExecutor):
    """Semgrep：本地源码静态审计（OWASP Top 10 规则）。"""

    def __init__(self, timeout: int = 600, require_confirmation: bool = True,
                 whitelist=None, allow_all: bool = False, confirm_callback=None,
                 credential_callback=None):
        super().__init__(tool_name="semgrep", timeout=timeout,
                         require_confirmation=require_confirmation, whitelist=whitelist,
                         allow_all=allow_all, confirm_callback=confirm_callback,
                         credential_callback=credential_callback)

    async def validate(self, step_input) -> bool:
        """本地审计：跳过主机白名单，仅校验路径非空 + 工具可用。"""
        path = (step_input.target or "").strip()
        if not path:
            return False
        return self._tool_available()

    def build_command(self, step_input, step_config) -> Optional[List[str]]:
        path = (step_config.get("path") or step_input.target or "").strip()
        if not path:
            self._build_error = "semgrep 需提供源码目录/文件路径"
            return None
        cmd = ["semgrep", "--config", str(step_config.get("config") or "p/owasp-top-ten")]
        cmd.append(path)
        return cmd
