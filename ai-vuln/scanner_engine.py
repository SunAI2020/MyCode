# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 扫描引擎模块"""
import os
import re
import socket
import logging
import time
import subprocess
import threading
import ipaddress
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from itertools import islice
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 0day专项扫描：通用厂商/操作系统/技术词——出现在大量 CVE 名称中、不具特异性，
# 用于过滤产品级匹配中的噪声，避免通用产品名（windows/microsoft 等）与数百条
# KEV 记录误匹配导致结果刷屏。
_GENERIC_PRODUCT_TOKENS = frozenset({
    # 操作系统 / 内核 / 平台
    'windows', 'linux', 'unix', 'kernel', 'macos', 'mac', 'android', 'ios',
    'ubuntu', 'debian', 'redhat', 'centos', 'fedora', 'suse', 'freebsd',
    'openbsd', 'netbsd', 'solaris', 'aix', 'embedded', 'firmware', 'mobile',
    # 浏览器 / 客户端
    'chrome', 'chromium', 'firefox', 'safari', 'edge', 'opera', 'browser',
    'internet', 'explorer',
    # 厂商（通用前缀，需配合具体产品才有意义）
    'microsoft', 'apple', 'google', 'adobe', 'oracle', 'cisco', 'apache',
    'mozilla', 'ibm', 'intel', 'amd', 'dell', 'lenovo', 'vmware', 'citrix',
    'juniper', 'fortinet', 'palo', 'alto',
    # 通用技术词
    'java', 'python', 'node', 'php', 'ruby', 'perl', 'runtime', 'framework',
    'server', 'client', 'desktop', 'service', 'system', 'network', 'remote',
    'access', 'code', 'execution', 'information', 'disclosure', 'injection',
    'denial', 'privilege', 'elevation', 'vulnerability', 'version', 'security',
    'management', 'enterprise', 'professional', 'edition', 'standard',
    'application', 'component', 'toolkit', 'database', 'sql',
    'http', 'https', 'tcp', 'udp', 'ssl', 'tls', 'ssh', 'ftp', 'smtp',
    'the', 'and', 'for', 'with',
})


def _has_specific_token(s: str) -> bool:
    """判断字符串是否含至少一个长度>=4 的非通用产品/厂商令牌。"""
    return any(tok not in _GENERIC_PRODUCT_TOKENS
               for tok in re.findall(r'[a-z0-9]{4,}', (s or '').lower()))


try:
    import nmap
    NMAP_AVAILABLE = True
except ImportError:
    NMAP_AVAILABLE = False
    logger.warning("nmap库未安装，使用内置扫描器")


class NetworkScanner:
    """网络扫描引擎"""

    COMMON_PORTS = {
        21: 'ftp', 22: 'ssh', 23: 'telnet', 25: 'smtp', 53: 'dns',
        80: 'http', 110: 'pop3', 143: 'imap', 443: 'https', 445: 'smb',
        993: 'imaps', 995: 'pop3s', 1433: 'mssql', 1521: 'oracle',
        3306: 'mysql', 3389: 'rdp', 5432: 'postgresql', 5900: 'vnc',
        6379: 'redis', 8080: 'http-proxy', 8443: 'https-alt', 27017: 'mongodb',
        2181: 'zookeeper', 9200: 'elasticsearch', 61616: 'activemq',
        5601: 'kibana', 50070: 'hadoop', 7077: 'spark', 9092: 'kafka'
    }

    DEFAULT_PORT_LIST = '21-23,25,53,80,110,143,443,445,993,995,1433,1521,3306,3389,5432,5900,6379,8080,8443,27017,2181,9200'

    # 服务版本探测指纹
    SERVICE_FINGERPRINTS = {
        'ssh': [b'SSH-'],
        'http': [b'HTTP/', b'Server:', b'<!DOCTYPE', b'<html'],
        'mysql': [b'mysql_native_password', b'MySQL'],
        'ftp': [b'220', b'FTP'],
        'smtp': [b'220', b'SMTP', b'ESMTP'],
        'pop3': [b'+OK', b'POP3'],
        'imap': [b'* OK', b'IMAP'],
        'rdp': [b'\x03\x00\x00'],
        'vnc': [b'RFB '],
    }

    def __init__(self, db=None, timeout: int = 5):
        self.db = db
        self.timeout = timeout
        self.nm = None
        self._scanning = False
        self._paused = False
        self._cancel = False
        self.progress_callback = None

        if NMAP_AVAILABLE:
            try:
                self.nm = nmap.PortScanner()
                logger.info("Nmap扫描器初始化成功")
            except Exception as e:
                logger.error(f"Nmap初始化失败: {e}")

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def parse_target(self, target: str) -> List[str]:
        """解析扫描目标"""
        targets = []
        if '-' in target and '/' not in target:
            match = re.match(r'(\d+\.\d+\.\d+\.)(\d+)-(\d+)', target)
            if match:
                prefix = match.group(1)
                start, end = int(match.group(2)), int(match.group(3))
                for i in range(start, min(end + 1, start + 256)):
                    targets.append(f"{prefix}{i}")
        elif '/' in target:
            # CIDR 展开：纯 Python 实现，不依赖 nmap（确定性、可测试）
            try:
                net = ipaddress.ip_network(target, strict=False)
                if net.num_addresses == 1:
                    # /32 单主机 CIDR：hosts() 为空，直接取该地址
                    targets = [str(net.network_address)]
                else:
                    targets = []
                    for i, ip in enumerate(net.hosts()):
                        if i >= 256:
                            logger.warning(f"CIDR {target} 主机数超过 256，仅扫描前 256 个地址")
                            break
                        targets.append(str(ip))
            except ValueError:
                targets = [target]
        else:
            targets = [target]
        return targets or [target]

    def _check_host_alive(self, host: str, timeout: int) -> bool:
        """检查主机是否存活（尝试多个常用端口）"""
        check_timeout = max(min(timeout, 3), 1)
        for port in [80, 443, 22, 3389, 8080, 3306]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(check_timeout)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    return True
            except:
                continue
        return False

    def _scan_port(self, host: str, port: int, timeout: int) -> Optional[Dict]:
        """扫描单个端口"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                service = self.COMMON_PORTS.get(port, 'unknown')
                version = self._detect_version(host, port, service)
                return {
                    'port': port, 'protocol': 'tcp', 'state': 'open',
                    'service': service, 'version': version
                }
        except:
            pass
        return None

    def _detect_version(self, host: str, port: int, service: str) -> str:
        """识别服务版本"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((host, port))

            probes = {'http': b'GET / HTTP/1.0\r\nHost: ' + host.encode() + b'\r\n\r\n',
                      'https': b'\x16\x03\x01\x00\xa1\x01\x00\x00\x9d\x03\x03',
                      'smtp': b'', 'ftp': b'', 'pop3': b'', 'imap': b'', 'ssh': b''}

            probe = probes.get(service, b'GET / HTTP/1.0\r\n\r\n')
            if probe:
                try:
                    sock.send(probe)
                    response = sock.recv(1024)
                    sock.close()
                    if response:
                        resp_str = response.decode('utf-8', errors='ignore')
                        lines = resp_str.split('\n')[:5]
                        for line in lines:
                            line = line.strip()
                            if line and len(line) < 200:
                                if any(kw in line.lower() for kw in ['server:', 'ssh-', 'mysql', 'apache', 'nginx', 'iis', 'tomcat', 'openssh']):
                                    return line[:100]
                        return lines[0][:100] if lines else ''
                except:
                    pass
            sock.close()
        except:
            pass
        return ''

    def _parse_port_string(self, port_str: str) -> List[int]:
        """解析端口字符串"""
        MAX_PORT = 65535
        MAX_PORTS = 10000
        ports = []
        for part in port_str.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                parts = part.split('-')
                if len(parts) != 2:
                    continue
                try:
                    start, end = int(parts[0]), int(parts[1])
                except ValueError:
                    continue
                if start < 1 or end < 1 or start > MAX_PORT or end > MAX_PORT:
                    continue
                if start > end:
                    start, end = end, start
                if end - start + 1 > MAX_PORTS:
                    continue
                ports.extend(range(start, end + 1))
            elif part.isdigit():
                p = int(part)
                if 1 <= p <= MAX_PORT:
                    ports.append(p)
        return sorted(set(ports))

    def scan_host_tcp(self, host: str, ports: str = None, timeout: int = None) -> Dict:
        """TCP端口扫描"""
        timeout = timeout or self.timeout
        results = {'host': host, 'status': 'down', 'ports': []}

        if not self._check_host_alive(host, timeout):
            return results

        results['status'] = 'up'
        port_list = self._parse_port_string(ports or self.DEFAULT_PORT_LIST)
        total = len(port_list)
        scanned = 0

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = {}
            for port in port_list:
                if self._cancel:
                    break
                futures[executor.submit(self._scan_port, host, port, timeout)] = port

            for future in as_completed(futures):
                scanned += 1
                result = future.result()
                if result:
                    results['ports'].append(result)
                if self.progress_callback and scanned % 5 == 0:
                    self.progress_callback(f"已扫描端口{scanned}/{total}")

        return results

    @staticmethod
    def _validate_target(target: str) -> bool:
        """校验目标是否为合法的网络地址，防止 nmap 参数注入"""
        if not target or not target.strip():
            return False
        # 拒绝包含 nmap CLI 选项标志的输入
        for token in target.split():
            if token.startswith('-'):
                return False
        # 只允许合法的网络目标字符: IP, hostname, CIDR, nmap范围语法
        if not re.match(r'^[A-Za-z0-9.\-/:_,*?~\[\]]+$', target):
            return False
        return True

    def scan_with_nmap(self, target: str, ports: str = None, arguments: str = '-sV -T4') -> Dict:
        """使用Nmap扫描"""
        if not NMAP_AVAILABLE or not self.nm:
            return self.scan_target(target, ports)

        if not self._validate_target(target):
            logger.error(f"无效的扫描目标 (可能包含注入字符): {target}")
            return {'target': target, 'hosts': [], 'error': '无效的扫描目标'}

        try:
            nm = nmap.PortScanner()
            ports = ports or self.DEFAULT_PORT_LIST
            nm.scan(hosts=target, ports=ports, arguments=arguments)
            results = {'target': target, 'hosts': []}
            targets_list = self.parse_target(target)
            scanned_ips = 0

            for host in nm.all_hosts():
                scanned_ips += 1
                if self.progress_callback and len(targets_list) > 1:
                    self.progress_callback(f"已扫描IP{scanned_ips}/{len(targets_list)}")

                host_info = {'ip': host, 'status': nm[host].state(), 'ports': []}
                if 'hostnames' in nm[host] and nm[host]['hostnames']:
                    host_info['hostname'] = nm[host]['hostnames'][0].get('name', '')

                for proto in ['tcp', 'udp']:
                    if proto in nm[host]:
                        for port, port_info in nm[host][proto].items():
                            host_info['ports'].append({
                                'port': port, 'protocol': proto,
                                'state': port_info.get('state', 'unknown'),
                                'service': port_info.get('name', 'unknown'),
                                'version': port_info.get('version', ''),
                                'product': port_info.get('product', '')
                            })

                if self.progress_callback and len(targets_list) == 1:
                    port_count = len(host_info['ports'])
                    if port_count > 0:
                        self.progress_callback(f"已扫描端口{port_count}/{port_count}")

                results['hosts'].append(host_info)
            return results
        except Exception as e:
            logger.error(f"Nmap扫描失败: {e}")
            return {'target': target, 'hosts': [], 'error': str(e)}

    def scan_target(self, target: str, ports: str = None, scan_type: str = 'quick') -> Dict:
        """扫描目标（优先使用Nmap）"""
        # 根据扫描类型设置端口和Nmap参数
        if scan_type == 'full' and ports is None:
            ports = '0-65535'
        elif scan_type == 'custom':
            ports = ports or self.DEFAULT_PORT_LIST

        # Nmap扫描（更准确）
        if NMAP_AVAILABLE and self.nm:
            nmap_args = '-sV -T4 --host-timeout 30s'
            if scan_type == 'full':
                nmap_args = '-sV -sC -T4 --host-timeout 60s'
            return self.scan_with_nmap(target, ports, nmap_args)

        # 回退到内置扫描
        targets = self.parse_target(target)
        results = {'target': target, 'hosts': []}
        target_count = len(targets)
        scanned_ips = 0

        for host in targets:
            if self._cancel:
                break
            while self._paused and not self._cancel:
                time.sleep(0.5)
            host_result = self.scan_host_tcp(host, ports)
            results['hosts'].append(host_result)
            scanned_ips += 1
            if self.progress_callback and target_count > 1:
                self.progress_callback(f"已扫描IP{scanned_ips}/{target_count}")

        return results

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def cancel(self):
        self._cancel = True
        self._paused = False

    # ============ 资产发现方法 ============
    def discover_assets(self, target_range: str, method: str = 'auto', callback=None) -> List[str]:
        """
        综合资产发现
        method: 'auto' 自动选择 | 'nmap' Nmap ping扫描 | 'icmp' Ping扫描 | 'tcp' TCP端口探测
        """
        if method == 'auto':
            return self._discover_auto(target_range, callback)

        hosts = []
        if method == 'nmap' and NMAP_AVAILABLE:
            hosts = self._discover_nmap(target_range, callback)
        elif method == 'icmp':
            hosts = self._discover_icmp(target_range, callback)
        elif method == 'tcp':
            hosts = self._discover_tcp(target_range, callback)
        else:
            hosts = self._discover_icmp(target_range, callback)

        return hosts

    def _discover_auto(self, target_range: str, callback=None) -> List[str]:
        """自动选择最佳发现方式"""
        hosts = []
        if NMAP_AVAILABLE and self.nm:
            try:
                hosts = self._discover_nmap(target_range, callback)
            except:
                pass
        if not hosts:
            if callback:
                callback('Nmap不可用或无结果，使用ICMP Ping扫描...')
            hosts = self._discover_icmp(target_range, callback)
        if not hosts:
            if callback:
                callback('ICMP无响应，使用TCP端口探测...')
            hosts = self._discover_tcp(target_range, callback)
        return hosts

    def _discover_nmap(self, target_range: str, callback=None) -> List[str]:
        """使用Nmap Ping扫描发现存活主机"""
        hosts = []
        try:
            nm = nmap.PortScanner()
            if callback:
                callback(f'正在使用Nmap Ping扫描 {target_range} ...')
            nm.scan(hosts=target_range, arguments='-sn -T4 --max-retries 1')
            all_up = [h for h in nm.all_hosts() if nm[h].state() == 'up']
            total = len(all_up)
            for i, host in enumerate(all_up, 1):
                hosts.append(host)
                if callback:
                    callback(f'正在扫描 {host} ... 已扫描 {i}/{total} 个IP')
        except Exception as e:
            logger.error(f"Nmap发现失败: {e}")
        return hosts

    def _discover_icmp(self, target_range: str, callback=None) -> List[str]:
        """使用系统Ping发现存活主机"""
        hosts = []
        targets = self.parse_target(target_range)
        total = len(targets)
        try:
            for i, host in enumerate(targets, 1):
                if self._cancel:
                    break
                if callback:
                    callback(f'正在扫描 {host} ... 已扫描 {i}/{total} 个IP')
                try:
                    creationflags = 0x08000000 if os.name == 'nt' else 0
                    ret = subprocess.run(
                        ['ping', '-n', '1', '-w', '500', host],
                        capture_output=True, timeout=1, creationflags=creationflags
                    )
                    if ret.returncode == 0:
                        hosts.append(host)
                        if callback:
                            callback(f'发现主机: {host}')
                except:
                    pass
        except Exception as e:
            logger.error(f"ICMP发现失败: {e}")
        return hosts

    def _discover_tcp(self, target_range: str, callback=None) -> List[str]:
        """使用TCP常用端口探测存活主机"""
        hosts = []
        targets = self.parse_target(target_range)
        total = len(targets)
        for i, host in enumerate(targets, 1):
            if self._cancel:
                break
            if callback:
                callback(f'正在扫描 {host} ... 已扫描 {i}/{total} 个IP')
            if self._check_host_alive(host, timeout=2):
                hosts.append(host)
                if callback:
                    callback(f'发现主机: {host}')
        return hosts


class VulnScanner:
    """漏洞扫描器 - 集成网络扫描和智能CVE匹配"""

    def __init__(self, db_manager=None, vuln_matcher=None):
        self.db = db_manager
        self.network_scanner = NetworkScanner(db_manager)
        self.vuln_matcher = vuln_matcher
        self._cve_lock = threading.Lock()  # 保护共享 sqlite 连接的并发访问

    def scan_target(self, target: str, ports: str = None,
                   scan_type: str = 'quick', weak_pass: bool = False,
                   zero_day_focus: bool = False) -> Dict[str, Any]:
        start_time = datetime.now()

        # 根据扫描类型设置参数
        if scan_type == 'quick':
            ports = ports or NetworkScanner.DEFAULT_PORT_LIST
            nmap_args = '-sV -T4'
        elif scan_type == 'full':
            ports = ports or '1-65535'
            nmap_args = '-sV -sC -T4'
        else:
            ports = ports or NetworkScanner.DEFAULT_PORT_LIST
            nmap_args = '-sV -T4'

        logger.info(f"VulnScanner开始扫描: {target}, 端口: {ports}")

        # 网络扫描
        if NMAP_AVAILABLE and self.network_scanner.nm:
            scan_result = self.network_scanner.scan_with_nmap(target, ports, nmap_args)
        else:
            scan_result = self.network_scanner.scan_target(target, ports)

        # 漏洞匹配
        vulnerabilities = self._match_vulnerabilities(scan_result)

        # 多类型设备专项检测（FR-11）：网络设备/安全设备/IoT/工控/国产化
        devices, device_findings = self._identify_devices(scan_result)
        vulnerabilities.extend(device_findings)

        # 蜜罐/欺骗资产识别（识别→标记→提示，不阻断扫描）
        honeypots, honeypot_findings = self._detect_honeypots(scan_result)
        vulnerabilities.extend(honeypot_findings)

        # 渗透测试：弱口令爆破（FR-10，可选）。命中结果结构化后独立并入，
        # 不经过相似度去重/富化，避免多组弱口令被误合并或字段被改写。
        weak_findings = []
        if weak_pass:
            weak_findings = self._scan_weak_passwords(
                scan_result, progress_callback=self.network_scanner.progress_callback)

        # 多因子风险评分（资产价值×威胁×脆弱性），供去重优先级与报告使用
        try:
            from risk_scoring import RiskScorer
            vulnerabilities = RiskScorer().score_many(vulnerabilities)
        except ImportError:
            pass

        # 相似度去重（AI 核验前，减少重复 CVE 的 AI token 消耗）
        # + evidence/remediation 结构化富化
        dedup_before = len(vulnerabilities)
        try:
            from vuln_dedup import VulnDeduplicator
            from vuln_enrich import enrich_vulnerabilities
            dedup = VulnDeduplicator().deduplicate(vulnerabilities)
            vulnerabilities = enrich_vulnerabilities(dedup['unique'])
            dedup_stats = {
                'before': dedup_before,
                'unique': len(dedup['unique']),
                'duplicates': len(dedup['duplicates']),
            }
        except ImportError as e:
            logger.warning(f"去重/富化模块导入失败，跳过: {e}")
            dedup_stats = {'before': dedup_before, 'unique': dedup_before, 'duplicates': 0}

        # 合并弱口令发现（已结构化，无需去重/富化）
        if weak_findings:
            vulnerabilities.extend(weak_findings)

        # 0day/活跃利用漏洞标记（最高优先级，重点提示）
        zero_day_count = self._flag_zero_day(vulnerabilities)

        # 0day漏洞专项扫描：对 CISA KEV 目录做产品级交叉比对，捕捉常规
        # CVE 匹配因版本缺失/产品名差异而遗漏的在野利用暴露。
        if zero_day_focus:
            focus_count = self._flag_zero_day_focus(scan_result, vulnerabilities)
            zero_day_count += focus_count
            # 专项追加的发现补齐 evidence/remediation 富化（与流水线其它发现结构一致）
            if focus_count:
                try:
                    from vuln_enrich import enrich_vulnerabilities
                    enrich_vulnerabilities(vulnerabilities[-focus_count:])
                except ImportError:
                    pass

        end_time = datetime.now()

        return {
            'target': target,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration': (end_time - start_time).total_seconds(),
            'scan_result': scan_result,
            'vulnerabilities': vulnerabilities,
            'devices': devices,
            'honeypots': honeypots,
            'honeypot_count': len(honeypots),
            'dedup_stats': dedup_stats,
            'weak_password_count': len(weak_findings),
            'zero_day_count': zero_day_count,
            'summary': self._generate_summary(vulnerabilities)
        }

    def scan_with_credentials(self, target: str, username: str, password: str = None,
                              private_key: str = None, os_type: str = 'linux-rpm',
                              port: int = 22) -> Dict[str, Any]:
        """认证扫描：用已知凭证登录主机枚举软件包并匹配 CVE（补无凭证覆盖缺口）。

        对标 Nessus/OpenVAS 的 credentialed scan。登录后采集已装软件包
        (product, version)，交给现有 _get_matched_cves 匹配 CVE。
        依赖 paramiko(SSH) / pywinrm(WinRM)，未安装时优雅降级。
        """
        try:
            from credentialed_scan import CredentialedScanner
        except ImportError as e:
            logger.warning(f"认证扫描模块导入失败: {e}")
            return {'status': 'error', 'reason': str(e),
                    'vulnerabilities': [], 'package_count': 0}

        result = CredentialedScanner().enumerate_packages(
            target, username, password=password, private_key=private_key,
            os_type=os_type, port=port)

        if result.get('status') != 'ok':
            return {'status': result.get('status', 'error'),
                    'reason': result.get('reason', ''),
                    'vulnerabilities': [], 'package_count': 0}

        vulnerabilities: List[Dict] = []
        with self._cve_lock:
            for pkg in result['packages']:
                matched = self._get_matched_cves(
                    service='', version=pkg.get('version', ''),
                    product=pkg.get('product', ''), port=None)
                for cve in matched:
                    vulnerabilities.append({
                        'host': target, 'port': None, 'protocol': 'tcp',
                        'service': '', 'version': pkg.get('version', ''),
                        'product': pkg.get('product', ''),
                        'cve_id': cve.get('cve_id'),
                        'cve_name': cve.get('name'),
                        'cvss_score': cve.get('cvss_score'),
                        'severity': cve.get('severity', 'INFO'),
                        'description': (cve.get('description', '') or '')[:500],
                        'affected_versions': '', 'references_url': '',
                        'finding_type': 'credentialed',
                    })

        return {'status': 'ok', 'reason': '',
                'vulnerabilities': vulnerabilities,
                'package_count': len(result['packages'])}

    def _match_vulnerabilities(self, scan_result: Dict) -> List[Dict]:
        """匹配漏洞 - 使用VulnMatcher进行智能匹配"""
        if self.vuln_matcher:
            vulnerabilities = []
            for host_info in scan_result.get('hosts', []):
                if host_info.get('status') != 'up':
                    continue
                host = host_info.get('ip') or host_info.get('host', '')
                ports_data = host_info.get('ports', [])
                vulns = self.vuln_matcher.match_vulnerabilities(host, ports_data)
                vulnerabilities.extend(vulns)
            return vulnerabilities

        # 回退：直接使用数据库搜索（并行匹配每个端口CVE）
        match_tasks = []
        for host_info in scan_result.get('hosts', []):
            if host_info.get('status') != 'up':
                continue
            host = host_info.get('ip') or host_info.get('host', '')
            for port_info in host_info.get('ports', []):
                if port_info.get('state') != 'open':
                    continue
                match_tasks.append((host, port_info))

        if not match_tasks:
            return []

        import threading
        _lock = threading.Lock()
        vulnerabilities = []

        def _match_port(host, port_info):
            service = port_info.get('service', '')
            version = port_info.get('version', '')
            product = port_info.get('product', '')
            port = port_info.get('port')
            # 共享 sqlite 连接非线程安全，串行化 DB 查询（CVE 匹配为轻量查询，串行无碍）
            with self._cve_lock:
                matched_cves = self._get_matched_cves(service, version, product, port)
            results = []
            if matched_cves:
                for cve in matched_cves:
                    affected_raw = cve.get('affected_products', '') or ''
                    if isinstance(affected_raw, list):
                        affected_raw = ', '.join(affected_raw)
                    results.append({
                        'host': host, 'port': port,
                        'protocol': port_info.get('protocol', 'tcp'),
                        'service': service,
                        'version': version or product or '',
                        'product': product or '',
                        'cve_id': cve.get('cve_id'),
                        'cvss_score': cve.get('cvss_score'),
                        'severity': cve.get('severity', 'INFO'),
                        'description': (cve.get('description', '') or '')[:500],
                        'affected_versions': affected_raw[:300],
                        'references_url': (cve.get('references_url', '') or '')[:300],
                        'patch_link': cve.get('patch_link', '') or '',
                        'cwe': cve.get('cwe', '') or '',
                        'match_confidence': cve.get('_match_confidence', ''),
                        'matched_by': cve.get('_matched_by', ''),
                    })
            else:
                # 无 CVE 命中（版本未知/无法识别产品）：输出开放服务兜底发现，不再堆 CVE
                results.append({
                    'host': host, 'port': port,
                    'protocol': port_info.get('protocol', 'tcp'),
                    'service': service,
                    'version': version or product or '',
                    'product': product or '',
                    'cve_id': None, 'severity': 'INFO',
                    'description': f'开放服务: {service} {version or product or ""} (端口{port})',
                    'affected_versions': '',
                    'references_url': '',
                    'finding_type': 'open_service',
                })
            return results

        with ThreadPoolExecutor(max_workers=min(8, len(match_tasks))) as executor:
            futures = {executor.submit(_match_port, h, pi): (h, pi) for h, pi in match_tasks}
            for future in as_completed(futures):
                with _lock:
                    vulnerabilities.extend(future.result())

        return vulnerabilities

    def _identify_devices(self, scan_result: Dict) -> Tuple[List[Dict], List[Dict]]:
        """多类型设备专项检测（FR-11）：识别设备类型并生成设备专项风险发现。

        覆盖五类资产：网络设备 / 网络安全设备 / IoT / 工控 / 国产化系统。
        返回 (devices, findings)：
        - devices: 识别出的设备分类列表（类别/厂商/产品/置信度）
        - findings: 设备专项风险发现，结构与漏洞列表对齐，可直接并入 vulnerabilities
        """
        try:
            from device_fingerprint import DeviceFingerprinter, generate_device_findings
        except ImportError as e:
            logger.warning(f"设备指纹模块导入失败: {e}")
            return [], []

        fingerprinter = DeviceFingerprinter()
        devices: List[Dict] = []
        findings: List[Dict] = []

        for host_info in scan_result.get('hosts', []):
            if host_info.get('status') != 'up':
                continue
            host = host_info.get('ip') or host_info.get('host', '')
            ports = host_info.get('ports', [])
            if not host or not ports:
                continue
            device = fingerprinter.identify_host(host, ports)
            host_info['device'] = device
            if not device.get('category'):
                continue
            devices.append(device)
            findings.extend(generate_device_findings(host, device, ports))

        return devices, findings

    def _detect_honeypots(self, scan_result: Dict) -> Tuple[List[Dict], List[Dict]]:
        """蜜罐/欺骗资产识别（识别→标记→提示，不阻断扫描）。

        调用 HoneypotDetector 对存活主机做签名/服务组合识别，命中后生成
        与漏洞列表结构对齐的发现。返回 (honeypots, findings)：
        - honeypots: 命中的蜜罐识别结果列表
        - findings:  蜜罐告警发现，可直接并入 vulnerabilities
        """
        try:
            from honeypot_detector import HoneypotDetector, generate_honeypot_findings
        except ImportError as e:
            logger.warning(f"蜜罐识别模块导入失败: {e}")
            return [], []

        detector = HoneypotDetector()
        honeypots: List[Dict] = detector.detect_scan_result(scan_result)

        findings: List[Dict] = []
        hosts_map = {h.get('ip') or h.get('host', ''): h for h in scan_result.get('hosts', [])}
        for hp in honeypots:
            host = hp.get('host', '')
            ports = hosts_map.get(host, {}).get('ports', [])
            findings.extend(generate_honeypot_findings(host, hp, ports))
        return honeypots, findings

    def _scan_weak_passwords(self, scan_result: Dict, progress_callback=None) -> List[Dict]:
        """渗透测试：对开放服务执行弱口令爆破（FR-10）。

        复用 threat_intel.db 的 weak_passwords 字典，对 SSH/FTP/MySQL/PostgreSQL/
        Redis/MongoDB/HTTP Basic/Telnet/RDP 等常见服务做保守爆破（连续失败即停，
        避免触发账户锁定）。命中结果转为漏洞结构，并入 vulnerabilities 供结果表
        与报告统一展示。
        """
        try:
            from weak_password_scanner import WeakPasswordScanner
        except ImportError as e:
            logger.warning(f"弱口令模块导入失败，跳过渗透测试: {e}")
            return []

        scanner = WeakPasswordScanner(db=self.db)
        findings = []
        for host_info in scan_result.get('hosts', []):
            if host_info.get('status') != 'up':
                continue
            host = host_info.get('ip') or host_info.get('host', '')
            if not host:
                continue
            services = [
                {'port': p.get('port'), 'service': p.get('service', '')}
                for p in host_info.get('ports', [])
                if p.get('state') == 'open'
            ]
            if not services:
                continue
            if progress_callback:
                progress_callback(f'渗透测试: 正在对 {host} 做弱口令检测...')
            try:
                results = scanner.scan_services(host, services, progress_callback=progress_callback)
            except Exception as e:
                logger.warning(f'弱口令检测 {host} 失败: {e}')
                continue
            for r in results:
                for cred in r.get('found', []):
                    username = cred.get('username', '')
                    password = cred.get('password', '')
                    protocol = r.get('protocol', '')
                    findings.append({
                        'host': host,
                        'port': r.get('port'),
                        'protocol': protocol or 'tcp',
                        'service': protocol or '',
                        'version': '',
                        'product': '',
                        'cve_id': None, 'cve_name': None, 'cvss_score': None,
                        'severity': 'HIGH',
                        'description': (
                            f"[弱口令] {host}:{r.get('port')} {protocol} 服务存在弱口令 "
                            f"{username}/{password}，可被未授权登录"
                        ),
                        'affected_versions': '', 'references_url': '',
                        'finding_type': 'weak_password',
                    })
        return findings

    def _get_matched_cves(self, service: str, version: str = '', product: str = '',
                          port: int = None) -> List[Dict]:
        """获取匹配的 CVE - 精确匹配（产品名一致 + 版本判定）。

        旧实现为关键词召回，会把无关产品的 CVE 挂到端口上（误报）。现改为：
        1. version_match.detect_product_key 归一化探测到的产品；
        2. 按规范键的召回词对 affected_products 做 LIKE 召回候选；
        3. version_match.cve_applies 逐条严格校验产品名 + 版本，命中才返回，
           并附带 match_confidence / matched_by。
        无法识别产品时返回空（由 _match_port 输出 open_service 兜底发现）。
        """
        if not self.db:
            return []
        from version_match import detect_product_key, recall_terms, cve_applies

        key = detect_product_key(product, service)
        if not key:
            return []

        candidates = {}
        for term in recall_terms(key):
            rows = []
            try:
                if hasattr(self.db, 'search_cve_by_product'):
                    rows = self.db.search_cve_by_product(term, limit=300)
                else:
                    rows = self.db.search_cve(keyword=term, min_cvss=0, limit=300)
            except Exception as e:
                logger.warning(f"CVE 召回失败 (term={term}): {e}")
                continue
            for cve in rows:
                cve_id = cve.get('cve_id', '')
                if cve_id and cve_id not in candidates:
                    candidates[cve_id] = cve

        matched = []
        detected_name = product or service
        for cve in candidates.values():
            verdict = cve_applies(cve, detected_name, version)
            if not verdict:
                continue
            item = dict(cve)
            item['_match_confidence'] = verdict['confidence']
            item['_matched_by'] = verdict['matched_by']
            matched.append(item)

        matched.sort(key=lambda x: (x.get('cvss_score') or 0), reverse=True)
        return matched

    def _flag_zero_day(self, vulnerabilities: List[Dict]) -> int:
        """0day/高危利用风险标记（最高优先级，重点提示）。

        采用双判据识别在野/高危利用风险：
        判据一：CISA KEV（Known Exploited Vulnerabilities，正被攻击者活跃利用）；
        判据二：EPSS 利用概率 > 0.9（高分，扩大在野利用识别覆盖，捕获未被 KEV
        收录但极可能被利用的漏洞）。
        任一命中即标记 is_0day 并将严重度提升至 CRITICAL、描述加醒目前缀；对
        KEV 中 known_ransomware 标记的条目追加更醒目的「已知勒索软件利用」警示。
        0day 是网络安全防护最重要的防护点。
        """
        if not self.db:
            return 0
        flagged = 0
        for v in vulnerabilities:
            cve_id = v.get('cve_id')
            if not cve_id:
                continue

            is_kev = False
            kev_rec = None
            epss_score = None
            try:
                if hasattr(self.db, 'is_kev'):
                    is_kev = bool(self.db.is_kev(cve_id))
            except Exception:
                is_kev = False

            if is_kev:
                try:
                    kev_rec = self.db.get_kev_by_cve(cve_id) if hasattr(self.db, 'get_kev_by_cve') else None
                except Exception:
                    kev_rec = None
            else:
                try:
                    ep = self.db.get_epss(cve_id) if hasattr(self.db, 'get_epss') else None
                    epss_score = ep.get('epss_score') if ep else None
                except Exception:
                    epss_score = None

            epss_high = epss_score is not None and epss_score > 0.9
            if not is_kev and not epss_high:
                continue

            v['is_0day'] = True
            v['kev'] = bool(is_kev)
            v['epss_high'] = epss_high
            if epss_score is not None:
                v['epss_score'] = epss_score

            ransomware = False
            if kev_rec:
                ransomware = bool(kev_rec.get('known_ransomware'))
                v['known_ransomware'] = ransomware
                v['kev_due_date'] = kev_rec.get('due_date') or ''
                v['kev_required_action'] = kev_rec.get('required_action') or ''

            if v.get('severity') not in ('CRITICAL',):
                v['severity'] = 'CRITICAL'

            # 前缀按最高优先级来源生成（勒索软件 > KEV 在野利用 > EPSS 高分）
            if is_kev and ransomware:
                prefix = '【已知勒索软件利用】'
            elif is_kev:
                prefix = '【0day/活跃利用】'
            else:
                prefix = '【0day/高危利用概率(EPSS)】'
            if not (v.get('description') or '').startswith(prefix):
                v['description'] = prefix + (v.get('description', '') or '')
            flagged += 1
        return flagged

    def _flag_zero_day_focus(self, scan_result: Dict, vulnerabilities: List[Dict]) -> int:
        """0day漏洞专项扫描 — 全量比对 CISA KEV 目录（最高优先级，重点提示）。

        常规扫描仅对"已匹配到 CVE"的结果做 KEV 精确 CVE-ID 标记；专项扫描额外
        将探测到的服务/产品/版本与 KEV 目录中每个已知被利用漏洞的名称做产品级
        交叉比对，捕捉因版本缺失或产品名差异而未被常规 CVE 匹配捕获的 0day/在野
        利用暴露。采用"整串包含 + 特异性"双重要求，避免通用产品名（windows/
        microsoft 等）与数百条 KEV 记录误匹配导致结果刷屏。
        """
        if not self.db or not hasattr(self.db, 'get_kev_list'):
            return 0
        try:
            kev_list = self.db.get_kev_list(limit=2000)
        except Exception as e:
            logger.warning(f"0day专项扫描: 获取KEV目录失败: {e}")
            return 0
        if not kev_list:
            return 0

        products = self._collect_scanned_products(scan_result)
        if not products:
            return 0

        # 预计算每个产品值的候选串与特异性（与 KEV 名称无关），避免在内层循环重复正则
        precomputed = []  # [(host, port, service, prod, [(candidate, has_specific), ...]), ...]
        for host, prod_items in products.items():
            for port, service, prod in prod_items:
                cands = self._product_candidates(prod)
                if cands:
                    precomputed.append((host, port, service, prod, cands))
        if not precomputed:
            return 0

        existing_cves = {v.get('cve_id') for v in vulnerabilities if v.get('cve_id')}

        added = 0
        for kev in kev_list:
            cve_id = kev.get('cve_id')
            name = (kev.get('vulnerability_name') or '').lower()
            if not cve_id or not name:
                continue
            if cve_id in existing_cves:
                continue  # 已通过常规 CVE 匹配 + _flag_zero_day 标记

            matched = None
            for host, port, service, prod, cands in precomputed:
                if any(cand in name and has_specific for cand, has_specific in cands):
                    matched = (host, port, service, prod)
                    break
            if not matched:
                continue
            host, port, service, prod = matched

            ransomware = bool(kev.get('known_ransomware'))
            prefix = '【已知勒索软件利用】' if ransomware else '【0day/活跃利用】'
            vulnerabilities.append({
                'host': host, 'port': port,
                'protocol': 'tcp', 'service': service, 'version': '',
                'product': prod, 'cve_id': cve_id,
                'cvss_score': '', 'severity': 'CRITICAL',
                'description': (
                    f"{prefix}{kev.get('vulnerability_name') or cve_id}"
                    f"（CISA KEV，{kev.get('date_added') or '在野利用中'}"
                    f"{'，已知勒索软件利用' if ransomware else ''}）。"
                    f"处置要求: {kev.get('required_action') or '请立即打补丁'}"
                ),
                'is_0day': True, 'kev': True, 'zero_day_match': 'product',
                'known_ransomware': ransomware,
            })
            existing_cves.add(cve_id)
            added += 1

            # 安全上限，避免异常数据导致结果爆炸
            if added >= 30:
                logger.warning("0day专项扫描: 命中超过30条，截断")
                break

        if added:
            logger.info(f"0day专项扫描: 新增 {added} 条在野利用暴露(产品级匹配)")
        return added

    @staticmethod
    def _collect_scanned_products(scan_result: Dict) -> Dict[str, List[Tuple[int, str, str]]]:
        """聚合探测到的服务/产品/版本（按主机分组，保留端口与服务）。

        仅保留原始字段值，不做版本拆分——版本拆分会产出 `microsoft windows` 这类
        过于通用的产品名导致误匹配，版本处理交由 `_product_candidates` 内部完成。
        """
        products = {}
        for host_info in scan_result.get('hosts', []):
            if host_info.get('status') != 'up':
                continue
            host = host_info.get('ip') or host_info.get('host', '')
            items = []
            seen = set()
            for p in host_info.get('ports', []):
                if p.get('state') != 'open':
                    continue
                port = p.get('port')
                service = (p.get('service') or '').lower().strip()
                for field in ('product', 'service', 'version'):
                    v = (p.get(field) or '').lower().strip()
                    if len(v) >= 3 and v not in seen:
                        seen.add(v)
                        items.append((port, service, v))
            if items:
                products[host] = items
        return products

    @staticmethod
    def _product_candidates(prod: str) -> List[Tuple[str, bool]]:
        """返回产品的候选匹配串及其特异性（候选串须整串出现在 KEV 名称中）。

        采用"整串包含 + 特异性"双重要求，避免通用产品名刷屏：
        1. 候选串（完整值或其去版本主体）长度 >= 6；
        2. 候选串整串出现在 KEV 名称中（由调用方判断，非逐 token 子串匹配）；
        3. 候选串含至少一个长度>=4 的非通用令牌（特异性）。
        """
        prod = ' '.join((prod or '').lower().split())
        if len(prod) < 6:
            return []
        candidates = [prod]
        # 去版本主体：截取首个数字之前的产品名（如 "openssh 8.2" -> "openssh"）
        m = re.match(r'^(.*?)[\s.-]*\d', prod)
        if m:
            base = m.group(1).strip()
            if len(base) >= 6 and base != prod:
                candidates.append(base)
        return [(c, _has_specific_token(c)) for c in candidates]

    def _generate_summary(self, vulnerabilities: List[Dict]) -> Dict[str, Any]:
        severity_counts = {}
        for vuln in vulnerabilities:
            sev = vuln.get('severity', 'UNKNOWN')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            'total': len(vulnerabilities),
            'by_severity': severity_counts,
            'high_critical': severity_counts.get('CRITICAL', 0) + severity_counts.get('HIGH', 0)
        }
