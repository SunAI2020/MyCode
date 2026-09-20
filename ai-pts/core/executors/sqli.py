"""
sqlmap 执行器（SQL 注入自动检测/利用，目标为 http/https URL）。
"""
from __future__ import annotations

import re
from typing import List, Optional

from core.executors.base import ToolExecutor

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


class SqlmapExecutor(ToolExecutor):
    """sqlmap：SQL 注入自动检测与利用。"""

    def __init__(self, timeout: int = 600, require_confirmation: bool = True,
                 whitelist=None, allow_all: bool = False, confirm_callback=None,
                 credential_callback=None):
        super().__init__(tool_name="sqlmap", timeout=timeout,
                         require_confirmation=require_confirmation, whitelist=whitelist,
                         allow_all=allow_all, confirm_callback=confirm_callback,
                         credential_callback=credential_callback)

    def build_command(self, step_input, step_config) -> Optional[List[str]]:
        url = (step_config.get("url") or step_input.target or "").strip()
        if not _URL_RE.match(url):
            self._build_error = "sqlmap 目标需为 http/https URL"
            return None
        cmd = ["sqlmap", "-u", url, "--batch"]
        if step_config.get("dbs"):
            cmd.append("--dbs")
        if step_config.get("level"):
            cmd += ["--level", str(step_config["level"])]
        return cmd
