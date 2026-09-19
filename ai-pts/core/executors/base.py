"""
统一外部工具执行器基类

每个专项工具（getshell / 提权 / 横向移动）实现为 ToolExecutor 子类，
内部通过 subprocess 调用外部工具或脚本，产出 StepOutput 供工作流引擎与
AI 编排器消费。默认保留人工确认闸门、目标白名单（fail-closed）与主机名校验。
"""
import asyncio
import shutil
import subprocess
import logging
import re
import time
from typing import List, Dict, Optional

from core.workflow import BaseExecutor, StepInput, StepOutput, StepStatus

logger = logging.getLogger(__name__)


class ToolExecutor(BaseExecutor):
    """封装外部工具调用的执行器基类"""

    def __init__(
        self,
        tool_name: str,
        timeout: int = 300,
        require_confirmation: bool = True,
        whitelist: Optional[List[str]] = None,
        allow_all: bool = False,
        confirm_callback=None,
    ):
        self.tool_name = tool_name
        self.timeout = timeout
        self.require_confirmation = require_confirmation
        self.whitelist = whitelist or []
        self.allow_all = allow_all
        self.confirm_callback = confirm_callback

    # ---- 辅助 ----

    @staticmethod
    def _extract_host(target: str) -> str:
        """从 "ip:port" / "http://host/path" 中提取主机"""
        t = (target or "").strip()
        for prefix in ("http://", "https://"):
            if t.startswith(prefix):
                t = t[len(prefix):]
        return t.split("/")[0].split(":")[0] if t else ""

    @staticmethod
    def _validate_host(host: str) -> bool:
        """主机名/IP 严格校验，拒绝含命令注入字符的目标"""
        return bool(re.fullmatch(r"[A-Za-z0-9.\-]+", host or ""))

    def _in_whitelist(self, host: str) -> bool:
        if self.allow_all:
            return True
        if not self.whitelist:
            return False  # 空白名单 + 未显式 allow_all = 拒绝（fail-closed）
        return host in self.whitelist

    def _tool_available(self, tool: str = None) -> bool:
        return shutil.which(tool or self.tool_name) is not None

    @staticmethod
    def _redact_cmd(cmd: List[str]) -> List[str]:
        """打码命令行中的凭据，避免泄露到日志/evidence：
        - user:pass@host -> user:***@host
        - -hashes <LM:NT> -> -hashes ***
        """
        out = []
        prev = None
        for c in cmd:
            if prev in ("-hashes", "--hashes"):
                out.append("***")
                prev = c
                continue
            if "@" in c:
                user, _, host = c.rpartition("@")
                if ":" in user:
                    name, _, _ = user.partition(":")
                    out.append(f"{name}:***@{host}")
                    prev = c
                    continue
            out.append(c)
            prev = c
        return out

    # ---- BaseExecutor 接口 ----

    async def validate(self, step_input: StepInput) -> bool:
        host = self._extract_host(step_input.target)
        if not host:
            logger.warning("无法解析目标主机: %r", step_input.target)
            return False
        if not self._validate_host(host):
            logger.warning("目标 %s 含非法字符，拒绝执行", host)
            return False
        if not self._in_whitelist(host):
            logger.warning("目标 %s 不在白名单内，拒绝执行", host)
            return False
        if not self._tool_available():
            logger.warning("工具 %s 未安装", self.tool_name)
            return False
        return True

    async def execute(self, step_input: StepInput, step_config: Dict) -> StepOutput:
        host = self._extract_host(step_input.target)

        # 人工确认闸门
        if self.require_confirmation:
            if self.confirm_callback is None:
                return StepOutput(
                    status=StepStatus.SKIPPED,
                    error=f"目标 {host} 需人工确认（未提供确认回调）",
                )
            try:
                ok = self.confirm_callback(host)
            except Exception as e:  # noqa: BLE001
                return StepOutput(status=StepStatus.SKIPPED, error=f"确认回调异常: {e}")
            if not ok:
                return StepOutput(status=StepStatus.SKIPPED, error=f"已取消对 {host} 的执行")

        cmd = self.build_command(step_input, step_config)
        if not cmd:
            return StepOutput(status=StepStatus.FAILED, error="无法构建命令（参数校验失败）")

        return await self._run(cmd)

    def build_command(self, step_input: StepInput, step_config: Dict) -> Optional[List[str]]:
        raise NotImplementedError

    async def rollback(self, step_output: StepOutput) -> bool:
        return True

    # ---- 内部 ----

    async def _run(self, cmd: List[str]) -> StepOutput:
        t0 = time.time()
        try:
            rc, out, err = await asyncio.to_thread(self._run_sync, cmd)
        except subprocess.TimeoutExpired:
            return StepOutput(status=StepStatus.FAILED, error=f"命令超时（{self.timeout}s）")
        except Exception as e:  # noqa: BLE001
            return StepOutput(status=StepStatus.FAILED, error=str(e))

        dt = round(time.time() - t0, 3)
        evidence = ["$ " + " ".join(self._redact_cmd(cmd)), (out or "").strip(), (err or "").strip()]
        result = {"returncode": rc, "stdout": out, "stderr": err}
        if rc == 0:
            return StepOutput(status=StepStatus.SUCCESS, result=result,
                              evidence=evidence, execution_time=dt)
        logger.warning(f"命令退出码 {rc}: {(err or '').strip()[:500]}")
        return StepOutput(status=StepStatus.FAILED, error=f"命令退出码 {rc}",
                          result=result, evidence=evidence, execution_time=dt)

    def _run_sync(self, cmd: List[str]):
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            encoding="utf-8",
            errors="replace",
        )
        return p.returncode, p.stdout or "", p.stderr or ""
