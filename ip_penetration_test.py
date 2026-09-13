#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IP地址渗透测试程序
功能：对指定IP地址进行端口扫描、服务识别和漏洞扫描
"""

import socket
import threading
import time
import re
from datetime import datetime

class IPPenetrationTester:
    def __init__(self, target_ip, start_port=1, end_port=65535, timeout=1):
        """初始化渗透测试器"""
        self.target_ip = target_ip
        self.start_port = start_port
        self.end_port = end_port
        self.timeout = timeout
        self.open_ports = []
        self.services = []
        self.vulnerabilities = []
        self.is_scanning = False
    
    def scan_port(self, port):
        """扫描单个端口"""
        if not self.is_scanning:
            return
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((self.target_ip, port))
            if result == 0:
                self.open_ports.append(port)
                service = self.identify_service(port)
                if service:
                    self.services.append((port, service))
                    vuln = self.check_vulnerability(port, service)
                    if vuln:
                        self.vulnerabilities.append((port, service, vuln))
            sock.close()
        except Exception:
            pass
    
    def identify_service(self, port):
        """识别端口上的服务"""
        common_services = {
            21: "FTP",
            22: "SSH",
            23: "Telnet",
            25: "SMTP",
            53: "DNS",
            80: "HTTP",
            443: "HTTPS",
            3306: "MySQL",
            3389: "RDP",
            5432: "PostgreSQL",
            6379: "Redis",
            27017: "MongoDB"
        }
        return common_services.get(port, "Unknown")
    
    def check_vulnerability(self, port, service):
        """检查常见漏洞"""
        vulnerabilities = {
            21: "FTP可能存在匿名访问漏洞",
            22: "SSH可能存在弱密码漏洞",
            23: "Telnet明文传输漏洞",
            25: "SMTP开放中继漏洞",
            80: "HTTP可能存在XSS或SQL注入漏洞",
            443: "HTTPS可能存在SSL/TLS漏洞",
            3306: "MySQL可能存在弱密码或远程访问漏洞",
            3389: "RDP可能存在暴力破解漏洞",
            5432: "PostgreSQL可能存在弱密码漏洞",
            6379: "Redis未授权访问漏洞",
            27017: "MongoDB未授权访问漏洞"
        }
        return vulnerabilities.get(port, None)
    
    def start_scan(self):
        """开始扫描"""
        self.is_scanning = True
        self.open_ports = []
        self.services = []
        self.vulnerabilities = []
        
        threads = []
        for port in range(self.start_port, self.end_port + 1):
            if not self.is_scanning:
                break
            thread = threading.Thread(target=self.scan_port, args=(port,))
            threads.append(thread)
            thread.start()
            # 限制并发线程数
            if len(threads) >= 100:
                for t in threads:
                    t.join()
                threads = []
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        self.is_scanning = False
    
    def stop_scan(self):
        """停止扫描"""
        self.is_scanning = False
    
    def generate_report(self):
        """生成扫描报告"""
        report = {
            "target_ip": self.target_ip,
            "scan_time": datetime.now().isoformat(),
            "open_ports": self.open_ports,
            "services": self.services,
            "vulnerabilities": self.vulnerabilities,
            "summary": {
                "total_open_ports": len(self.open_ports),
                "total_services": len(self.services),
                "total_vulnerabilities": len(self.vulnerabilities)
            }
        }
        return report
    
    def validate_ip(self, ip):
        """验证IP地址格式"""
        pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        if not re.match(pattern, ip):
            return False
        
        parts = ip.split('.')
        for part in parts:
            if int(part) > 255:
                return False
        return True
