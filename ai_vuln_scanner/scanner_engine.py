# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 扫描引擎模块"""
import os
import re
import socket
import logging
import time
import subprocess
import threading
from typing import List, Dict, Optional, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            if NMAP_AVAILABLE and self.nm:
                try:
                    self.nm.scan(hosts=target, ports='1-10', arguments='-sn -T4')
                    targets = list(self.nm.all_hosts())
                except:
                    targets = [target]
            else:
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
        ports = []
        for part in port_str.split(','):
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                ports.extend(range(int(start), int(end) + 1))
            elif part.isdigit():
                ports.append(int(part))
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

    def scan_with_nmap(self, target: str, ports: str = None, arguments: str = '-sV -T4') -> Dict:
        """使用Nmap扫描"""
        if not NMAP_AVAILABLE or not self.nm:
            return self.scan_target(target, ports)

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
