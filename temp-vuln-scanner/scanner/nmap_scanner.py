"""
Nmap 扫描模块
基于 python-nmap 实现端口扫描和服务识别
"""
import nmap
import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from database.models import ScannedHost, ScannedService
from config.settings import SCAN

logger = logging.getLogger(__name__)


@dataclass
class ScanProgress:
    """扫描进度"""
    current_host: str
    total_hosts: int
    scanned_hosts: int
    current_port: int
    total_ports: int
    scanned_ports: int
    status: str  # scanning/paused/completed/error


class NmapScanner:
    """Nmap 扫描器"""
    
    def __init__(self, timeout: int = None):
        """
        初始化扫描器
        
        Args:
            timeout: 扫描超时时间（秒）
        """
        self.timeout = timeout or SCAN['default_timeout']
        self.nm = nmap.PortScanner()
        self._paused = False
        self._cancelled = False
    
    def parse_targets(self, target: str) -> List[str]:
        """
        解析扫描目标
        
        Args:
            target: 目标字符串（单个 IP、IP 范围、CIDR 或文件路径）
            
        Returns:
            List[str]: IP 地址列表
        """
        import os
        import ipaddress
        
        ips = []
        
        # 检查是否是文件路径
        if os.path.isfile(target):
            with open(target, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        ips.extend(self.parse_targets(line))
            return list(set(ips))
        
        # 检查是否是 CIDR 格式
        if '/' in target:
            try:
                network = ipaddress.ip_network(target, strict=False)
                return [str(ip) for ip in network.hosts()]
            except ValueError:
                pass
        
        # 检查是否是 IP 范围 (如 192.168.1.1-100)
        if '-' in target:
            try:
                parts = target.split('-')
                if len(parts) == 2:
                    start_parts = parts[0].split('.')
                    end_parts = parts[1].split('.')
                    
                    if len(start_parts) == 4 and len(end_parts) == 4:
                        base = '.'.join(start_parts[:3])
                        start = int(start_parts[3])
                        end = int(end_parts[3])
                        
                        for i in range(start, end + 1):
                            ips.append(f"{base}.{i}")
                        return ips
            except (ValueError, IndexError):
                pass
        
        # 单个 IP 或主机名
        try:
            ipaddress.ip_address(target)
            return [target]
        except ValueError:
            # 可能是主机名，尝试解析
            import socket
            try:
                addr = socket.gethostbyname(target)
                return [addr]
            except socket.gaierror:
                logger.warning(f"无法解析目标：{target}")
                return []
    
    def scan_host(
        self,
        host: str,
        ports: str = None,
        scan_type: str = 'T',  # 默认使用 TCP 连接扫描 (不需要 root 权限)
        version_detect: bool = True,
        os_detect: bool = False
    ) -> Tuple[Optional[ScannedHost], List[ScannedService]]:
        """
        扫描单个主机
        
        Args:
            host: 目标主机 IP
            ports: 端口范围，如 "1-1000,8080"
            scan_type: 扫描类型 (S=SYN, T=TCP, U=UDP)
            version_detect: 是否进行版本检测
            os_detect: 是否进行操作系统检测
            
        Returns:
            Tuple[ScannedHost, List[ScannedService]]: 主机信息和服务列表
        """
        try:
            # 构建扫描参数
            # scan_type: 'T' (TCP) 或 'S' (SYN)，转换为 -sT 或 -sS
            arguments = f'-s{scan_type}'
            
            if version_detect:
                arguments += ' -sV'
            
            if os_detect:
                arguments += ' -O'
            
            arguments += f' -T4 --host-timeout {self.timeout}'
            
            # 执行扫描
            if ports:
                self.nm.scan(host, ports=ports, arguments=arguments)
            else:
                # 使用常用端口
                common_ports = ','.join(map(str, SCAN['common_ports']))
                self.nm.scan(host, ports=common_ports, arguments=arguments)
            
            # 检查主机状态
            if host not in self.nm.all_hosts() or self.nm[host].state() != 'up':
                return ScannedHost(ip=host, status='down'), []
            
            # 获取主机信息
            host_info = self.nm[host]
            # MAC 地址仅在非本地网络扫描时可用，127.0.0.1 等本地地址没有 MAC
            mac_addr = None
            try:
                mac_addr = host_info.mac()
            except (KeyError, AttributeError):
                pass  # 本地回环地址没有 MAC 地址
            scanned_host = ScannedHost(
                ip=host,
                hostname=host_info.hostname() if host_info.hostname() else None,
                mac_address=mac_addr,
                status='up',
                scanned_at=datetime.now().isoformat()
            )
            
            # 获取操作系统信息
            if os_detect and 'osmatch' in host_info:
                os_matches = host_info['osmatch']
                if os_matches:
                    scanned_host.os = os_matches[0]['name']
                    scanned_host.os_version = os_matches[0]['accuracy']
            
            # 获取服务信息
            services = []
            for proto in host_info.all_protocols():
                if proto in ['tcp', 'udp']:
                    ports_info = host_info[proto]
                    for port, port_info in ports_info.items():
                        service = ScannedService(
                            host_ip=host,
                            port=int(port),
                            protocol=proto,
                            service_name=port_info.get('name', 'unknown'),
                            product=port_info.get('product', ''),
                            version=port_info.get('version', ''),
                            extra_info=port_info.get('extrainfo', ''),
                            banner=port_info.get('product', '') + ' ' + port_info.get('version', '')
                        )
                        services.append(service)
            
            logger.info(f"扫描完成：{host}, 发现 {len(services)} 个服务")
            return scanned_host, services
            
        except Exception as e:
            logger.error(f"扫描主机 {host} 失败：{e}")
            return ScannedHost(ip=host, status='error'), []
    
    async def scan_hosts_async(
        self,
        hosts: List[str],
        ports: str = None,
        max_concurrent: int = None
    ) -> List[Tuple[ScannedHost, List[ScannedService]]]:
        """
        异步扫描多个主机
        
        Args:
            hosts: 主机列表
            ports: 端口范围
            max_concurrent: 最大并发数
            
        Returns:
            List[Tuple[ScannedHost, List[ScannedService]]]: 扫描结果列表
        """
        max_concurrent = max_concurrent or SCAN['max_concurrent_hosts']
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scan_with_semaphore(host):
            async with semaphore:
                if self._cancelled:
                    return None
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.scan_host(host, ports)
                )
                return result
        
        tasks = [scan_with_semaphore(host) for host in hosts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"扫描任务异常：{result}")
            elif result is not None:
                valid_results.append(result)
        
        return valid_results
    
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
        self._cancelled = True
        logger.info("扫描已取消")
    
    def get_scan_stats(self) -> Dict:
        """获取扫描统计"""
        return {
            'hosts_scanned': len(self.nm.all_hosts()),
            'total_hosts': len(self.nm.all_hosts()),
        }


def create_scanner(timeout: int = None) -> NmapScanner:
    """创建扫描器实例"""
    return NmapScanner(timeout=timeout)
