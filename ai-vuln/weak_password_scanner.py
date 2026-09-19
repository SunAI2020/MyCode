# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 弱口令检测模块

接入核心扫描能力的弱口令/默认口令检测。复用 threat_intel.db 的
weak_passwords 字典，按协议分发到对应 handler（HTTP Basic / FTP / SSH /
MySQL / PostgreSQL / Redis / MongoDB / RDP / Telnet）。
无客户端库的服务如实返回不支持原因（可选依赖：paramiko/pymysql/psycopg2/
redis/pymongo/xfreerdp），不静默。
"""
import time
import socket
import subprocess
import shutil
import logging
from typing import List, Dict, Optional, Any


def _verify_for_url(url: str) -> bool:
    """按目标归属决定 TLS 证书校验：公网强制校验，内网关闭。

    复用 ssrf_guard 的地址归属判定；导入失败回退到不校验（旧行为）。
    """
    try:
        from ssrf_guard import tls_verify
        return tls_verify(url)
    except ImportError:
        return False
from ftplib import FTP, all_errors

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 抑制自签名证书告警（弱口令探测目标常为自签名/无效证书，属预期场景）
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False

try:
    import pymysql
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import pymongo
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

# 内置兜底字典（db 不可用时的最小集，与 database.py 播种一致）
BUILTIN_CREDENTIALS = [
    {'username': 'admin', 'password': 'admin'},
    {'username': 'admin', 'password': '123456'},
    {'username': 'admin', 'password': 'password'},
    {'username': 'admin', 'password': 'admin123'},
    {'username': 'root', 'password': 'root'},
    {'username': 'root', 'password': '123456'},
    {'username': 'root', 'password': 'password'},
    {'username': 'root', 'password': 'toor'},
]

# 协议 → 是否支持真实爆破（有标准库/可选库客户端）
SUPPORTED_PROTOCOLS = {'http', 'https', 'ftp', 'ssh', 'mysql', 'postgresql',
                       'redis', 'mongodb', 'rdp', 'telnet'}

# 服务名 → 协议映射（对接扫描引擎的 service 字段）
SERVICE_PROTOCOL_MAP = {
    'http': 'http', 'https': 'https', 'http-proxy': 'http',
    'ftp': 'ftp', 'ssh': 'ssh',
    'mysql': 'mysql', 'postgresql': 'postgresql', 'postgres': 'postgresql',
    'redis': 'redis', 'mongodb': 'mongodb', 'mongod': 'mongodb',
    'ms-wbt-server': 'rdp', 'rdp': 'rdp', 'telnet': 'telnet',
}


class BaseAuthHandler:
    """认证 handler 基类"""

    protocol = 'generic'

    def check(self, host: str, port: int, username: str, password: str,
              timeout: int = 5, **kwargs) -> bool:
        raise NotImplementedError


class HTTPBasicAuthHandler(BaseAuthHandler):
    """HTTP Basic 认证爆破"""

    protocol = 'http'

    def check(self, host, port, username, password, timeout=5,
              https=False, path='/', **kwargs) -> bool:
        import requests
        scheme = 'https' if https or port in (443, 8443) else 'http'
        url = f'{scheme}://{host}:{port}{path}'
        try:
            # 控制请求：不带凭据探测，确认服务端确实要求 HTTP Basic 认证。
            # 否则任意返回 200 的站点（非 Basic 认证、开放首页、登录页）都会被误判为"弱口令命中"。
            probe = requests.get(url, timeout=timeout, verify=_verify_for_url(url),
                                 allow_redirects=False)
            if probe.status_code != 401:
                return False
            if 'basic' not in (probe.headers.get('WWW-Authenticate', '') or '').lower():
                return False
            # 确认使用 Basic 认证后，再带凭据验证：200=凭据正确，401=凭据错误
            r = requests.get(url, auth=(username, password), timeout=timeout,
                             verify=_verify_for_url(url), allow_redirects=False)
            return r.status_code == 200
        except requests.RequestException:
            return False


class FTPHandler(BaseAuthHandler):
    """FTP 登录爆破"""

    protocol = 'ftp'

    def check(self, host, port, username, password, timeout=5, **kwargs) -> bool:
        try:
            ftp = FTP()
            ftp.connect(host, port, timeout=timeout)
            ftp.login(username, password)
            try:
                ftp.quit()
            except Exception:
                ftp.close()
            return True
        except all_errors:
            return False
        except Exception:
            return False


class SSHHandler(BaseAuthHandler):
    """SSH 登录爆破（需 paramiko，可选）"""

    protocol = 'ssh'

    def __init__(self):
        self.available = PARAMIKO_AVAILABLE

    def check(self, host, port, username, password, timeout=5, **kwargs) -> bool:
        if not PARAMIKO_AVAILABLE:
            return False
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(host, port=port, username=username, password=password,
                           timeout=timeout, allow_agent=False, look_for_keys=False,
                           banner_timeout=timeout, auth_timeout=timeout)
            client.close()
            return True
        except Exception:
            return False


class MySQLHandler(BaseAuthHandler):
    """MySQL 登录爆破（需 pymysql，可选）"""

    protocol = 'mysql'

    def __init__(self):
        self.available = PYMYSQL_AVAILABLE

    def check(self, host, port, username, password, timeout=5, **kwargs) -> bool:
        if not PYMYSQL_AVAILABLE:
            return False
        try:
            conn = pymysql.connect(host=host, port=port, user=username, password=password,
                                   connect_timeout=timeout, read_timeout=timeout,
                                   write_timeout=timeout)
            conn.close()
            return True
        except Exception:
            return False


class PostgreSQLHandler(BaseAuthHandler):
    """PostgreSQL 登录爆破（psycopg2）"""

    protocol = 'postgresql'

    def __init__(self):
        self.available = PSYCOPG2_AVAILABLE

    def check(self, host, port, username, password, timeout=5, **kwargs) -> bool:
        if not PSYCOPG2_AVAILABLE:
            return False
        try:
            conn = psycopg2.connect(host=host, port=port, user=username, password=password,
                                    dbname='postgres', connect_timeout=timeout)
            conn.close()
            return True
        except Exception:
            return False


class RedisHandler(BaseAuthHandler):
    """Redis 登录爆破（redis-py，可选）"""

    protocol = 'redis'

    def __init__(self):
        self.available = REDIS_AVAILABLE

    def check(self, host, port, username, password, timeout=5, **kwargs) -> bool:
        if not REDIS_AVAILABLE:
            return False
        try:
            r = redis.Redis(host=host, port=port, username=username or None, password=password,
                            socket_connect_timeout=timeout, socket_timeout=timeout)
            r.ping()
            return True
        except Exception:
            return False


class MongoDBHandler(BaseAuthHandler):
    """MongoDB 登录爆破（pymongo，可选）"""

    protocol = 'mongodb'

    def __init__(self):
        self.available = PYMONGO_AVAILABLE

    def check(self, host, port, username, password, timeout=5, **kwargs) -> bool:
        if not PYMONGO_AVAILABLE:
            return False
        try:
            client = pymongo.MongoClient(
                host, port, username=username, password=password,
                authSource='admin', serverSelectionTimeoutMS=timeout * 1000,
                connectTimeoutMS=timeout * 1000)
            client.admin.command('ping')
            client.close()
            return True
        except Exception:
            return False


class RDPHandler(BaseAuthHandler):
    """RDP 登录爆破（xfreerdp +auth-only，可选；无客户端时不可用）"""

    protocol = 'rdp'

    def __init__(self):
        self.available = bool(shutil.which('xfreerdp') or shutil.which('rdesktop'))

    def check(self, host, port, username, password, timeout=5, **kwargs) -> bool:
        if not self.available:
            return False
        try:
            cmd = ['xfreerdp', f'/v:{host}:{port}', f'/u:{username}', f'/p:{password}',
                   '/cert:ignore', '+auth-only', '/timeout:10000']
            r = subprocess.run(cmd, capture_output=True, timeout=timeout + 15)
            return r.returncode == 0
        except Exception:
            return False


class TelnetHandler(BaseAuthHandler):
    """Telnet 登录爆破（纯 socket，stdlib，保守判定）"""

    protocol = 'telnet'
    available = True

    def check(self, host, port, username, password, timeout=5, **kwargs) -> bool:
        try:
            s = socket.create_connection((host, port), timeout=timeout)
            s.settimeout(timeout)
            # 读取登录提示
            banner = b''
            try:
                while len(banner) < 4096:
                    chunk = s.recv(1024)
                    if not chunk:
                        break
                    banner += chunk
                    low = banner.lower()
                    if b'login:' in low or b'username:' in low or b'user:' in low:
                        break
            except socket.timeout:
                pass
            s.sendall((username + '\r\n').encode('ascii', errors='ignore'))
            time.sleep(0.3)
            try:
                s.recv(1024)
            except socket.timeout:
                pass
            s.sendall((password + '\r\n').encode('ascii', errors='ignore'))
            time.sleep(0.5)
            data = b''
            try:
                while len(data) < 4096:
                    chunk = s.recv(1024)
                    if not chunk:
                        break
                    data += chunk
            except socket.timeout:
                pass
            s.close()
            text = data.decode('utf-8', errors='ignore').lower()
            # 保守：出现明确失败特征即失败；出现 shell 提示符才判成功
            for marker in ('login:', 'username:', 'login incorrect', 'login failed',
                           'invalid', 'denied', 'authentication failed', 'password:'):
                if marker in text:
                    return False
            for marker in ('$ ', '# ', '> ', 'last login', 'welcome'):
                if marker in text:
                    return True
            return False
        except Exception:
            return False


HANDLER_REGISTRY: Dict[str, BaseAuthHandler] = {
    'http': HTTPBasicAuthHandler(),
    'https': HTTPBasicAuthHandler(),
    'ftp': FTPHandler(),
    'ssh': SSHHandler(),
    'mysql': MySQLHandler(),
    'postgresql': PostgreSQLHandler(),
    'redis': RedisHandler(),
    'mongodb': MongoDBHandler(),
    'rdp': RDPHandler(),
    'telnet': TelnetHandler(),
}


class WeakPasswordScanner:
    """弱口令检测编排器"""

    def __init__(self, db=None, max_attempts_per_service: int = 200,
                 delay_between_attempts: float = 0.5,
                 max_failures_before_break: int = 3):
        self.db = db
        self._weak_db = None
        self.max_attempts_per_service = max_attempts_per_service
        self.delay = delay_between_attempts
        # 账户锁定规避：连续失败达到阈值即停止该服务，避免触发目标账户锁定
        self.max_failures_before_break = max_failures_before_break

    def _get_weak_db(self):
        """返回持有弱口令字典的 DB。

        弱口令字典存在 threat_intel.db（ThreatIntelDB），但调用方（如
        scanner_engine）传入的是 CVEDatabase，二者不同。传入的 db 若无
        get_weak_passwords 方法，则改用 ThreatIntelDB。
        """
        if self.db is not None and hasattr(self.db, 'get_weak_passwords'):
            return self.db
        if self._weak_db is None:
            try:
                from database import ThreatIntelDB
                self._weak_db = ThreatIntelDB()
            except Exception as e:
                logger.warning(f"初始化弱口令字典库失败: {e}")
                return None
        return self._weak_db

    def get_credentials(self, protocol: Optional[str] = None) -> List[Dict]:
        """获取弱口令字典（优先 db，回退内置）"""
        db = self._get_weak_db()
        if db:
            try:
                creds = db.get_weak_passwords(protocol=protocol,
                                              limit=self.max_attempts_per_service)
                if creds:
                    return creds
            except Exception as e:
                logger.warning(f"读取弱口令字典失败: {e}")
        return BUILTIN_CREDENTIALS

    @staticmethod
    def map_protocol(service: str) -> Optional[str]:
        """服务名 → 协议"""
        return SERVICE_PROTOCOL_MAP.get(service)

    def is_supported(self, protocol: str) -> bool:
        return protocol in SUPPORTED_PROTOCOLS

    def scan(self, host: str, port: int, protocol: str,
             credentials: Optional[List[Dict]] = None,
             progress_callback=None, https: bool = False) -> Dict[str, Any]:
        """对单个服务执行弱口令检测"""
        result: Dict[str, Any] = {
            'host': host, 'port': port, 'protocol': protocol,
            'service_supported': True, 'found': [], 'attempts': 0, 'reason': '',
        }

        if not self.is_supported(protocol):
            result['service_supported'] = False
            result['reason'] = f'协议 {protocol} 无标准库客户端，暂不支持爆破（可扩展 paramiko/pymysql 等）'
            return result

        handler = HANDLER_REGISTRY.get(protocol)
        if handler is None:
            result['service_supported'] = False
            result['reason'] = f'协议 {protocol} 无对应 handler'
            return result

        if not getattr(handler, 'available', True):
            result['service_supported'] = False
            result['reason'] = f'协议 {protocol} 的客户端库不可用，弱口令检测跳过'
            return result

        creds = credentials if credentials is not None else self.get_credentials(protocol)
        consecutive_failures = 0
        for i, cred in enumerate(creds):
            username = cred.get('username', '')
            password = cred.get('password', '')
            if progress_callback and i % 20 == 0:
                progress_callback(f'弱口令检测 {host}:{port} 尝试 {i}/{len(creds)}')
            if self.delay > 0 and i > 0:
                time.sleep(self.delay)
            if handler.check(host, port, username, password, https=https):
                result['found'].append({'username': username, 'password': password,
                                        'protocol': protocol})
                # 命中即停：找到一组弱口令即可证明存在弱口令风险
                break
            result['attempts'] += 1
            consecutive_failures += 1
            # 账户锁定规避：连续失败达到阈值即停止，避免触发目标账户锁定策略
            if consecutive_failures >= self.max_failures_before_break:
                result['reason'] = f'连续失败 {consecutive_failures} 次，为避免触发账户锁定已停止'
                break

        return result

    def scan_services(self, host: str, services: List[Dict],
                      credentials: Optional[List[Dict]] = None,
                      progress_callback=None) -> List[Dict]:
        """批量检测：services 为 [{'port':80,'service':'http'}, ...]"""
        results = []
        for svc in services:
            port = svc.get('port')
            service = svc.get('service', '')
            protocol = self.map_protocol(service)
            if not protocol:
                continue
            r = self.scan(host, port, protocol, credentials=credentials,
                          progress_callback=progress_callback,
                          https=(service == 'https'))
            results.append(r)
        return results
