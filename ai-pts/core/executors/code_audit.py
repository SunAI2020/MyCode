"""
Semgrep 执行器（本地源码静态审计，目标为本地路径，非远程攻击面）。
"""
from __future__ import annotations

import json
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
        # --no-error：semgrep 命中漏洞时退出码为 1，加此参数让「发现漏洞」不再被误判为执行失败
        cmd = ["semgrep", "--json", "--no-error",
               "--config", str(step_config.get("config") or "p/owasp-top-ten")]
        cmd.append(path)
        return cmd

    def _parse(self, result):
        """解析 semgrep --json 输出，提取发现（规则/路径/行号/严重度/消息）。"""
        out = result.get("stdout") or result.get("stderr") or ""
        try:
            start = out.find("{")
            if start == -1:
                return {"findings": [], "count": 0}
            data = json.loads(out[start:])
        except Exception:
            return {"findings": [], "count": 0}
        results = data.get("results", []) if isinstance(data, dict) else []
        findings = []
        for r in results:
            extra = r.get("extra") or {}
            findings.append({
                "rule_id": r.get("check_id", ""),
                "path": r.get("path", ""),
                "line": (r.get("start") or {}).get("line", ""),
                "severity": extra.get("severity", ""),
                "message": (extra.get("message", "") or "")[:200],
            })
        return {"findings": findings, "count": len(findings)}
