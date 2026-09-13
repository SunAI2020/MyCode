# -*- coding: utf-8 -*-
"""
AI Vuln Scanner Pro - 扫描引擎模块
集成Nmap进行网络扫描和服务识别
"""
import os
import re
import socket
import logging
import asyncio
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 尝试导入nmap
try:
    import nmap
    NMAP_AVAILABLE = True
except ImportError:
    NMAP_AVAILABLE = False
    logger.warning("nmap库未安装，网络扫描功能将受限")


class NetworkScanner:
    """网络扫描引擎"""

    # 常见服务端口映射
    COMMON_PORTS = {
        21: 'ftp', 22: 'ssh', 23: 'telnet', 25: 'smtp', 53: 'dns',
        80: 'http', 110: 'pop3', 143: 'imap', 443: 'https', 445: 'smb',
        993: 'imaps', 995: 'pop3s', 1433: 'mssql', 1521: 'oracle',
        3306: 'mysql', 3389: 'rdp', 5432: 'postgresql', 5900: 'vnc',
        6379: 'redis', 8080: 'http-proxy', 8443: 'https-alt', 27017: 'mongodb'
    }

    # 常用端口列表
    DEFAULT_PORT_LIST = '21-23,25,53,80,110,143,443,445,993,995,1433,1521,3306,3389,5432,5900,6379,8080,8443,27017'

    def __init__(self, db_manager=None, timeout: int = 5):
        """初始化扫描器"""
        self.db = db_manager
        self.timeout = timeout
        self.nm = None
        self._scanning = False
        self._paused = False
        self._cancel = False

        if NMAP_AVAILABLE:
            try:
                self.nm = nmap.PortScanner()
                logger.info("Nmap扫描器初始化成功")
            except Exception as e:
                logger.error(f"Nmap初始化失败: {e}")

    def parse_target(self, target: str) -> List[str]:
        """解析扫描目标"""
        targets = []

        # IP范围 (192.168.1.1-254)
        if '-' in target and not '/':
            match = re.match(r'(\d+\.\d+\.\d+\.)(\d+)-(\d+)', target)
            if match:
                prefix = match.group(1)
                start, end = int(match.group(2)), int(match.group(3))
                for i in range(start, end + 1):
                    targets.append(f"{prefix}{i}")

        # CIDR notation (192.168.1.0/24)
        elif '/' in target:
            if NMAP_AVAILABLE and self.nm:
                # 使用nmap解析CIDR
                try:
                    self.nm.scan(hosts=target, ports='-')
                    targets = list(self.nm.all_hosts())
                except Exception as e:
                    logger.error(f"CIDR解析失败: {e}")
                    # 回退到简单方法
                    targets = [target]
            else:
                targets = [target]

        # 单个IP或域名
        else:
            targets = [target]

        return targets

    def resolve_hostname(self, hostname: str) -> Optional[str]:
        """解析主机名到IP"""
        try:
            return socket.gethostbyname(hostname)
        except Exception as e:
            logger.error(f"解析主机名失败 {hostname}: {e}")
            return None

    def scan_host_tcp(self, host: str, ports: str = None,
                      timeout: int = None) -> Dict[str, Any]:
        """TCP端口扫描（无nmap版本）"""
        timeout = timeout or self.timeout
        results = {
            'host': host,
            'status': 'down',
            'ports': []
        }

        # 检测主机是否存活
        if not self._check_host_alive(host, timeout):
            return results

        results['status'] = 'up'

        # 解析端口
        port_list = self._parse_port_string(ports or self.DEFAULT_PORT_LIST)

        for port in port_list:
            if self._cancel:
                break

            while self._paused:
                if self._cancel:
                    break
                import time
                time.sleep(0.5)

            service_info = self._scan_port(host, port, timeout)
            if service_info:
                results['ports'].append(service_info)

        return results

    def _check_host_alive(self, host: str, timeout: int) -> bool:
        """检查主机是否存活"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            # 尝试连接常用端口
            for port in [80, 443, 22]:
                try:
                    result = sock.connect_ex((host, port))
                    sock.close()
                    if result == 0:
                        return True
                except:
                    continue

            # TCP ping
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                result = sock.connect_ex((host, 80))
                sock.close()
                return result == 0
            except:
                return False
        except:
            return False

    def _scan_port(self, host: str, port: int, timeout: int) -> Optional[Dict]:
        """扫描单个端口"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                # 端口开放，尝试识别服务
                service = self.COMMON_PORTS.get(port, 'unknown')
                version = self._detect_version(host, port, service)

                return {
                    'port': port,
                    'protocol': 'tcp',
                    'state': 'open',
                    'service': service,
                    'version': version
                }
        except Exception as e:
            pass

        return None

    def _detect_version(self, host: str, port: int, service: str) -> str:
        """尝试识别服务版本"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((host, port))

            # 发送通用探测请求
            probes = {
                'http': b'GET / HTTP/1.0\r\n\r\n',
                'https': b'GET / HTTP/1.0\r\n\r\n',
                'ssh': b'',
                'ftp': b'',
                'mysql': b'',
            }

            probe = probes.get(service, b'')
            if probe:
                sock.send(probe)

                try:
                    response = sock.recv(1024)
                    sock.close()

                    # 解析响应获取版本信息
                    if response:
                        response_str = response.decode('utf-8', errors='ignore')
                        # 提取服务器Banner
                        for line in response_str.split('\n'):
                            if 'Server:' in line or 'SSH-' in line or 'MySQL' in line:
                                return line.strip()
                except:
                    pass
        except:
            pass

        return ''

    def _parse_port_string(self, port_str: str) -> List[int]:
        """解析端口字符串"""
        ports = []
        parts = port_str.split(',')

        for part in parts:
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                ports.extend(range(int(start), int(end) + 1))
            else:
                ports.append(int(part))

        return sorted(set(ports))

    def scan_with_nmap(self, target: str, ports: str = None,
                      arguments: str = '-sV -T4') -> Dict[str, Any]:
        """使用Nmap进行扫描"""
        if not NMAP_AVAILABLE or not self.nm:
            logger.warning("Nmap不可用，使用内置扫描器")
            return self.scan_target(target, ports)

        try:
            nm = nmap.PortScanner()
            scan_args = arguments

            if not ports:
                ports = self.DEFAULT_PORT_LIST

            logger.info(f"开始扫描: {target} 端口: {ports}")

            nm.scan(hosts=target, ports=ports, arguments=scan_args)

            results = {
                'target': target,
                'hosts': []
            }

            for host in nm.all_hosts():
                host_info = {
                    'ip': host,
                    'status': nm[host].state(),
                    'ports': []
                }

                # 获取主机名
                if 'hostnames' in nm[host] and nm[host]['hostnames']:
                    host_info['hostname'] = nm[host]['hostnames'][0].get('name', '')

                # 遍历端口
                if 'tcp' in nm[host]:
                    for port, port_info in nm[host]['tcp'].items():
                        host_info['ports'].append({
                            'port': port,
                            'protocol': 'tcp',
                            'state': port_info.get('state', 'unknown'),
                            'service': port_info.get('name', 'unknown'),
                            'version': port_info.get('version', ''),
                            'product': port_info.get('product', '')
                        })

                results['hosts'].append(host_info)

            return results

        except Exception as e:
            logger.error(f"Nmap扫描失败: {e}")
            return {'target': target, 'hosts': [], 'error': str(e)}

    def scan_target(self, target: str, ports: str = None) -> Dict[str, Any]:
        """扫描目标"""
        targets = self.parse_target(target)

        results = {
            'target': target,
            'hosts': []
        }

        # 计算总IP数
        target_count = len(targets)
        scanned_ips = 0

        # 单个IP时传递原始回调，多个IP时抑制端口进度
        if target_count == 1:
            # 单个IP扫描：显示端口扫描进度
            scan_callback = self.progress_callback
        else:
            # 多个IP扫描：暂时禁用端口进度回调，由本方法统一发送IP进度
            original_callback = self.progress_callback
            self.progress_callback = None

        for host in targets:
            if self._cancel:
                break

            # 使用线程池加速扫描
            with ThreadPoolExecutor(max_workers=10) as executor:
                host_result = executor.submit(self.scan_host_tcp, host, ports).result()
                results['hosts'].append(host_result)

                scanned_ips += 1
                # 发送IP扫描进度 (多个IP时显示)
                if target_count > 1 and self.progress_callback is None and original_callback:
                    original_callback(f"已扫描IP{scanned_ips}/{target_count}")

        # 恢复原始回调
        if target_count > 1:
            self.progress_callback = original_callback

        return results

    def scan_async(self, targets: List[str], ports: str = None,
                  callback=None) -> List[Dict]:
        """异步扫描多个目标"""
        results = []
        self._scanning = True
        self._cancel = False

        def scan_wrapper(target):
            if self._cancel:
                return None
            result = self.scan_target(target, ports)
            if callback:
                callback(result)
            return result

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = executor.map(scan_wrapper, targets)
            results = [r for r in futures if r]

        self._scanning = False
        return results

    def pause(self):
        """暂停扫描"""
        self._paused = True
        logger.info("扫描已暂停")

    def resume(self):
        """恢复扫描"""
        self._paused = False
        logger.info("扫描已恢复")

    def cancel(self):
        """取消扫描"""
        self._cancel = True
        self._paused = False
        logger.info("扫描已取消")


class VulnScanner:
    """漏洞扫描器 - 结合网络扫描和CVE匹配"""

    def __init__(self, db_manager=None, threat_intel=None):
        """初始化漏洞扫描器"""
        self.db = db_manager
        self.network_scanner = NetworkScanner(db_manager)
        self.threat_intel = threat_intel

    def scan_target(self, target: str, ports: str = None,
                   scan_type: str = 'quick') -> Dict[str, Any]:
        """执行完整扫描"""
        start_time = datetime.now()

        # 根据扫描类型设置参数
        if scan_type == 'quick':
            ports = ports or NetworkScanner.DEFAULT_PORT_LIST
            nmap_args = '-sV -T4'
        elif scan_type == 'full':
            ports = '1-1000'
            nmap_args = '-sV -sC -T4'
        else:
            ports = ports or NetworkScanner.DEFAULT_PORT_LIST
            nmap_args = '-sV -T4'

        # 网络扫描
        logger.info(f"开始网络扫描: {target}")

        if NMAP_AVAILABLE:
            scan_result = self.network_scanner.scan_with_nmap(target, ports, nmap_args)
        else:
            scan_result = self.network_scanner.scan_target(target, ports)

        # 漏洞匹配
        vulnerabilities = self._match_vulnerabilities(scan_result)

        end_time = datetime.now()

        return {
            'target': target,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration': (end_time - start_time).total_seconds(),
            'scan_result': scan_result,
            'vulnerabilities': vulnerabilities,
            'summary': self._generate_summary(vulnerabilities)
        }

    def _match_vulnerabilities(self, scan_result: Dict) -> List[Dict]:
        """匹配漏洞"""
        vulnerabilities = []

        for host_info in scan_result.get('hosts', []):
            if host_info.get('status') != 'up':
                continue

            host = host_info.get('ip')

            for port_info in host_info.get('ports', []):
                if port_info.get('state') != 'open':
                    continue

                service = port_info.get('service', '')
                version = port_info.get('version', '')

                # 从数据库匹配CVE
                matched_cves = self._get_matched_cves(service, version)

                if matched_cves:
                    for cve in matched_cves:
                        vulnerabilities.append({
                            'host': host,
                            'port': port_info.get('port'),
                            'protocol': port_info.get('protocol', 'tcp'),
                            'service': service,
                            'version': version,
                            'cve_id': cve.get('cve_id'),
                            'cve_name': cve.get('name'),
                            'cvss_score': cve.get('cvss_score'),
                            'severity': cve.get('severity'),
                            'description': cve.get('description', '')[:200]
                        })
                else:
                    # 无匹配CVE时，添加服务信息
                    vulnerabilities.append({
                        'host': host,
                        'port': port_info.get('port'),
                        'protocol': port_info.get('protocol', 'tcp'),
                        'service': service,
                        'version': version,
                        'cve_id': None,
                        'severity': 'INFO',
                        'description': f'服务识别: {service} {version}'
                    })

        return vulnerabilities

    def _get_matched_cves(self, service: str, version: str = None) -> List[Dict]:
        """获取匹配的CVE"""
        if not self.db:
            return []

        # 搜索相关CVE
        cves = self.db.search_cve(
            keyword=service,
            min_cvss=7.0,  # 高危以上
            limit=5
        )

        return cves

    def _generate_summary(self, vulnerabilities: List[Dict]) -> Dict[str, Any]:
        """生成扫描摘要"""
        severity_counts = {}
        for vuln in vulnerabilities:
            sev = vuln.get('severity', 'UNKNOWN')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            'total': len(vulnerabilities),
            'by_severity': severity_counts,
            'high_critical': severity_counts.get('CRITICAL', 0) + severity_counts.get('HIGH', 0)
        }


# 测试
if __name__ == '__main__':
    scanner = NetworkScanner()

    print("测试目标解析:")
    print(f"  单IP: {scanner.parse_target('192.168.1.1')}")
    print(f"  IP范围: {scanner.parse_target('192.168.1.1-10')}")

    print("\n测试端口扫描 (127.0.0.1)...")
    result = scanner.scan_host_tcp('127.0.0.1', '80,443,22,3306')

    print(f"主机状态: {result['status']}")
    print(f"开放端口数: {len(result['ports'])}")

    for port in result['ports']:
        print(f"  端口 {port['port']}: {port['service']} ({port['version']})")