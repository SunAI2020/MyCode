"""
提权专项执行器

- SecretsDumpExecutor：impacket secretsdump 提取 SAM/LSA/NTDS 凭据哈希
- LinPEASExecutor：通过 SSH 在目标上执行 LinPEAS/WinPEAS 枚举提权线索
"""
import logging
import shutil
import sys
from typing import List, Optional

from core.executors.base import ToolExecutor

logger = logging.getLogger(__name__)


class SecretsDumpExecutor(ToolExecutor):
    """impacket secretsdump 凭据哈希提取（提权/横向的凭据来源）"""

    def __init__(
        self,
        timeout: int = 300,
        require_confirmation: bool = True,
        whitelist=None,
        allow_all: bool = False,
        confirm_callback=None,
    ):
        super().__init__(
            tool_name="secretsdump.py",
            timeout=timeout,
            require_confirmation=require_confirmation,
            whitelist=whitelist,
            allow_all=allow_all,
            confirm_callback=confirm_callback,
        )

    def build_command(self, step_input, step_config) -> Optional[List[str]]:
        host = self._extract_host(step_input.target)
        if not host or not self._validate_host(host):
            return None

        creds = step_input.credentials or {}
        username = creds.get("username") or step_config.get("username") or "administrator"
        password = creds.get("password") or step_config.get("password") or ""
        hashes = creds.get("hashes") or step_config.get("hashes") or ""
        domain = creds.get("domain") or step_config.get("domain") or ""

        user_at = f"{domain}/{username}" if domain else username
        # impacket 脚本是 Python 源码，Windows 上直接执行会报 WinError 193，
        # 必须用当前解释器执行脚本全路径（同 getshell.py 的 ImpacketExecExecutor）。
        script = shutil.which(self.tool_name)
        if not script:
            return None
        cmd = [sys.executable, script]
        if hashes:
            cmd += ["-hashes", hashes]
            target = f"{user_at}@{host}"
        elif password:
            target = f"{user_at}:{password}@{host}"
        else:
            target = f"{user_at}@{host}"
        cmd += [target]
        return cmd


class LinPEASExecutor(ToolExecutor):
    """通过 SSH 在目标上执行 PEAS 枚举脚本（LinPEAS / WinPEAS）"""

    def __init__(
        self,
        peas_remote_path: str = "/tmp/linpeas.sh",
        shell: str = "bash",
        timeout: int = 600,
        require_confirmation: bool = True,
        whitelist=None,
        allow_all: bool = False,
        confirm_callback=None,
    ):
        super().__init__(
            tool_name="ssh",
            timeout=timeout,
            require_confirmation=require_confirmation,
            whitelist=whitelist,
            allow_all=allow_all,
            confirm_callback=confirm_callback,
        )
        self.peas_remote_path = peas_remote_path
        self.shell = shell

    def build_command(self, step_input, step_config) -> Optional[List[str]]:
        host = self._extract_host(step_input.target)
        if not host or not self._validate_host(host):
            return None

        creds = step_input.credentials or {}
        username = creds.get("username") or step_config.get("username") or "root"
        peas_path = step_config.get("peas_path") or self.peas_remote_path
        shell = step_config.get("shell") or self.shell
        remote = f"{username}@{host}"

        # 假设脚本已上传到目标；执行并捕获输出
        # accept-new：首次连接未知靶机自动接受，但主机密钥变更时拒绝（防 MITM，优于 no）
        return ["ssh", "-o", "StrictHostKeyChecking=accept-new", remote, f"{shell} {peas_path}"]
