# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 认证扫描模块（credentialed scan）

对标 Nessus/OpenVAS 的认证扫描：用【已知有效凭证】登录目标主机，枚举已装
软件包（Linux rpm/dpkg，Windows 注册表已装软件），再把 (product, version)
交给现有 CVE 匹配引擎，补无凭证扫描覆盖不到的「补丁缺失」类漏洞。

与弱口令爆破（weak_password_scanner.py）的本质区别：
- 弱口令爆破：猜密码，发现「弱密码」这个漏洞
- 认证扫描：用已知凭证登录，进主机内部查已装软件包 → 匹配 CVE

依赖可选：paramiko(SSH) / pywinrm(WinRM)。未安装时优雅降级为 unsupported。

安全：SSH 一律校验主机密钥（RejectPolicy + 系统 known_hosts，可用
known_hosts 参数指定密钥文件），WinRM 一律走 HTTPS(5986) 并校验证书。
不提供明文传输或跳过校验的降级路径。
"""
import logging
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False

try:
    import winrm
    WINRM_AVAILABLE = True
except ImportError:
    WINRM_AVAILABLE = False


# 各 OS 的软件包枚举命令
PACKAGE_QUERY_COMMANDS = {
    'linux-rpm': "rpm -qa --qf '%{NAME} %{VERSION}-%{RELEASE}\\n' 2>/dev/null",
    'linux-deb': "dpkg-query -W -f='${Package} ${Version}\\n' 2>/dev/null",
    'windows': ("Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*,"
                " HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*"
                " | Where-Object { $_.DisplayName -and $_.DisplayVersion }"
                " | ForEach-Object { \"$($_.DisplayName) $($_.DisplayVersion)\" }"),
}


def build_package_query(os_type: str) -> str:
    """根据 OS 类型返回软件包枚举命令。未知类型回退到 linux-rpm。"""
    return PACKAGE_QUERY_COMMANDS.get(os_type, PACKAGE_QUERY_COMMANDS['linux-rpm'])


def parse_package_output(os_type: str, raw_output: str) -> List[Dict[str, str]]:
    """解析枚举输出 → [{product, version}]。

    兼容 rpm（name version-release）、dpkg（name version）、
    Windows 已装软件（DisplayName DisplayVersion）三种输出。
    以最后一个空白为界：前为名称（可含空格，如 Windows 软件名），后为版本。
    """
    if not raw_output:
        return []
    packages: List[Dict[str, str]] = []
    for line in raw_output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue
        name, version = parts[0].strip(), parts[1].strip()
        if not name or not version:
            continue
        packages.append({'product': name, 'version': version})
    return packages


class CredentialedScanner:
    """认证扫描器 — 用已知凭证登录主机枚举已装软件包"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def enumerate_packages(self, host: str, username: str, password: str = None,
                           private_key: str = None, os_type: str = 'linux-rpm',
                           port: int = 22, known_hosts: str = None) -> Dict:
        """枚举目标主机已装软件包。

        返回 {'status': 'ok'|'unsupported'|'error', 'packages': [...], 'reason': ...}
        known_hosts: 可选，指定 SSH known_hosts 文件路径（否则加载系统默认）。
        """
        if os_type == 'windows':
            return self._winrm_enumerate(host, username, password)
        return self._ssh_enumerate(host, username, password, private_key, os_type, port, known_hosts)

    def _ssh_enumerate(self, host, username, password, private_key, os_type, port, known_hosts) -> Dict:
        if not PARAMIKO_AVAILABLE:
            return {'status': 'unsupported', 'packages': [],
                    'reason': 'paramiko 未安装（SSH 认证扫描不可用）'}
        try:
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            if known_hosts:
                client.load_host_keys(known_hosts)
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
            client.connect(host, port=port, username=username, password=password,
                           key_filename=private_key, timeout=self.timeout)
            _stdin, stdout, stderr = client.exec_command(build_package_query(os_type))
            raw = stdout.read().decode('utf-8', errors='ignore')
            err = stderr.read().decode('utf-8', errors='ignore')
            exit_status = stdout.channel.recv_exit_status()
            client.close()
            if exit_status != 0:
                return {'status': 'error', 'packages': [],
                        'reason': f'软件包枚举命令失败(exit={exit_status}): {err[:200]}'}
            if not raw.strip():
                return {'status': 'error', 'packages': [],
                        'reason': '枚举命令无输出（目标可能非 rpm/dpkg 系或命令被限制）'}
            return {'status': 'ok', 'packages': parse_package_output(os_type, raw), 'reason': ''}
        except Exception as e:
            logger.warning(f"SSH 认证扫描失败 {host}: {e}")
            return {'status': 'error', 'packages': [], 'reason': str(e)}

    def _winrm_enumerate(self, host, username, password) -> Dict:
        if not WINRM_AVAILABLE:
            return {'status': 'unsupported', 'packages': [],
                    'reason': 'pywinrm 未安装（WinRM 认证扫描不可用）'}
        try:
            session = winrm.Session(f'https://{host}:5986/wsman', auth=(username, password),
                                    transport='ssl', server_cert_validation='validate')
            r = session.run_ps(build_package_query('windows'))
            raw = r.std_out.decode('utf-8', errors='ignore')
            if getattr(r, 'status_code', 0) != 0:
                err = r.std_err.decode('utf-8', errors='ignore') if getattr(r, 'std_err', None) else ''
                return {'status': 'error', 'packages': [],
                        'reason': f'WinRM 命令失败(status={r.status_code}): {err[:200]}'}
            if not raw.strip():
                return {'status': 'error', 'packages': [],
                        'reason': '注册表枚举无输出（目标可能无已安装软件）'}
            return {'status': 'ok', 'packages': parse_package_output('windows', raw), 'reason': ''}
        except Exception as e:
            logger.warning(f"WinRM 认证扫描失败 {host}: {e}")
            return {'status': 'error', 'packages': [], 'reason': str(e)}


__all__ = [
    'PACKAGE_QUERY_COMMANDS', 'PARAMIKO_AVAILABLE', 'WINRM_AVAILABLE',
    'build_package_query', 'parse_package_output', 'CredentialedScanner',
]
