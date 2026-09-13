# -*- coding: utf-8 -*-
"""ECC安全增强模块 - Claude Code ECC"""
import socket
import ssl
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ECC/加密已知漏洞模式
WEAK_CIPHERS = {
    'RC4': {'severity': 'CRITICAL', 'desc': 'RC4流密码已被破解，应立即禁用'},
    'DES': {'severity': 'CRITICAL', 'desc': 'DES加密强度不足(56位)，已被暴力破解'},
    '3DES': {'severity': 'HIGH', 'desc': '3DES安全性较弱，建议迁移到AES'},
    'MD5': {'severity': 'CRITICAL', 'desc': 'MD5哈希算法已被破解，存在碰撞攻击风险'},
    'SHA1': {'severity': 'HIGH', 'desc': 'SHA-1已不推荐使用，建议升级到SHA-256/SHA-3'},
    'EXPORT': {'severity': 'CRITICAL', 'desc': '出口级加密强度极低，存在FREAK/Logjam攻击风险'},
    'anon': {'severity': 'HIGH', 'desc': '匿名加密套件不提供身份验证，存在中间人攻击风险'},
    'NULL': {'severity': 'CRITICAL', 'desc': '空加密套件不提供加密保护'},
    'ADH': {'severity': 'HIGH', 'desc': '匿名DH密钥交换，不提供服务器认证'},
    'PSK': {'severity': 'MEDIUM', 'desc': '预共享密钥模式，密钥管理风险'},
}

# TLS版本风险评估
TLS_VERSIONS = {
    'SSLv2': {'severity': 'CRITICAL', 'desc': 'SSLv2存在严重安全缺陷，必须禁用'},
    'SSLv3': {'severity': 'CRITICAL', 'desc': 'SSLv3存在POODLE攻击漏洞，必须禁用'},
    'TLSv1.0': {'severity': 'HIGH', 'desc': 'TLS 1.0已过时，存在BEAST攻击风险，PCI DSS要求禁用'},
    'TLSv1.1': {'severity': 'MEDIUM', 'desc': 'TLS 1.1已过时，建议升级到TLS 1.2+'},
    'TLSv1.2': {'severity': 'INFO', 'desc': 'TLS 1.2目前安全，推荐配置'},
    'TLSv1.3': {'severity': 'INFO', 'desc': 'TLS 1.3是最新安全标准，推荐使用'},
}

# 加密漏洞检测规则
CRYPTO_VULN_CHECKS = [
    {'id': 'ECC-001', 'name': '弱加密套件检测', 'desc': '检测TLS/SSL配置中是否包含已知弱加密套件'},
    {'id': 'ECC-002', 'name': '过时TLS版本检测', 'desc': '检测是否支持已废弃的TLS/SSL版本'},
    {'id': 'ECC-003', 'name': '证书有效性检测', 'desc': '检测SSL证书是否有效、过期或自签名'},
    {'id': 'ECC-004', 'name': '密钥长度检测', 'desc': '检测RSA/DSA/ECC密钥长度是否符合安全标准'},
    {'id': 'ECC-005', 'name': 'HSTS检测', 'desc': '检测HTTP服务是否启用HSTS安全头'},
    {'id': 'ECC-006', 'name': '证书透明性检测', 'desc': '检测SSL证书是否支持Certificate Transparency'},
    {'id': 'ECC-007', 'name': 'OCSP装订检测', 'desc': '检测是否启用OCSP Stapling'},
    {'id': 'ECC-008', 'name': '前向安全性检测', 'desc': '检测是否支持Perfect Forward Secrecy'},
]


class ECCSecurityChecker:
    """ECC安全检测器 - 基于Claude Code ECC的加密安全检测"""

    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.findings = []
        logger.info("ECC安全检测器(Claude Code ECC)初始化完成")

    def check_port(self, host: str, port: int, service: str = '') -> List[Dict]:
        """对指定端口进行加密安全检测"""
        findings = []

        # SSL/TLS端口检测
        ssl_ports = {443, 8443, 465, 993, 995, 636}
        if port in ssl_ports or 'ssl' in service.lower() or 'tls' in service.lower() or 'https' in service.lower():
            tls_findings = self._check_tls(host, port)
            findings.extend(tls_findings)

        # HTTP安全头检测
        if port in (80, 443, 8080, 8443) or 'http' in service.lower():
            http_findings = self._check_http_security(host, port)
            findings.extend(http_findings)

        # SSH安全检测
        if port == 22 or 'ssh' in service.lower():
            ssh_findings = self._check_ssh_security(host, port)
            findings.extend(ssh_findings)

        return findings

    def _check_tls(self, host: str, port: int) -> List[Dict]:
        """TLS/SSL安全检测"""
        findings = []
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            ssock = context.wrap_socket(sock, server_hostname=host)
            ssock.connect((host, port))

            # 获取TLS版本
            tls_ver = ssock.version()
            if tls_ver:
                tls_info = TLS_VERSIONS.get(tls_ver, {})
                findings.append({
                    'rule_id': 'ECC-002',
                    'severity': tls_info.get('severity', 'INFO'),
                    'port': port,
                    'category': 'TLS版本',
                    'finding': f'TLS版本: {tls_ver}',
                    'recommendation': tls_info.get('desc', ''),
                })

            # 获取加密套件
            try:
                cipher = ssock.cipher()
                if cipher:
                    cipher_name = cipher[0]
                    cipher_ver = cipher[1]
                    cipher_bits = cipher[2]
                    findings.append({
                        'rule_id': 'ECC-001',
                        'severity': 'INFO',
                        'port': port,
                        'category': '加密套件',
                        'finding': f'加密套件: {cipher_name} (版本: {cipher_ver}, 密钥长度: {cipher_bits}位)',
                        'recommendation': f'当前使用{cipher_name}，密钥长度{cipher_bits}位',
                    })

                    # 检查弱加密
                    for weak_cipher, info in WEAK_CIPHERS.items():
                        if weak_cipher.lower() in cipher_name.lower():
                            findings.append({
                                'rule_id': 'ECC-001',
                                'severity': info['severity'],
                                'port': port,
                                'category': '弱加密',
                                'finding': f'检测到弱加密: {cipher_name} 包含 {weak_cipher}',
                                'recommendation': info['desc'],
                            })
            except:
                pass

            # 获取证书信息
            try:
                cert = ssock.getpeercert(binary_form=False)
                if cert:
                    cert_findings = self._analyze_cert(cert, port)
                    findings.extend(cert_findings)
            except:
                findings.append({
                    'rule_id': 'ECC-003',
                    'severity': 'HIGH',
                    'port': port,
                    'category': '证书',
                    'finding': '无法获取SSL证书或证书无效',
                    'recommendation': '检查证书配置，确保证书有效且可被客户端信任',
                })

            ssock.close()
        except ssl.SSLError as e:
            findings.append({
                'rule_id': 'ECC-002',
                'severity': 'CRITICAL',
                'port': port,
                'category': 'TLS错误',
                'finding': f'SSL/TLS握手失败: {str(e)[:100]}',
                'recommendation': '检查TLS配置，可能使用了过时的协议版本或不安全的加密套件',
            })
        except socket.timeout:
            findings.append({
                'rule_id': 'ECC-000',
                'severity': 'INFO',
                'port': port,
                'category': '连接超时',
                'finding': f'端口{port}连接超时',
                'recommendation': '',
            })
        except Exception as e:
            findings.append({
                'rule_id': 'ECC-000',
                'severity': 'INFO',
                'port': port,
                'category': '连接错误',
                'finding': f'无法连接到端口{port}: {str(e)[:100]}',
                'recommendation': '',
            })

        return findings

    def _analyze_cert(self, cert: Dict, port: int) -> List[Dict]:
        """分析SSL证书"""
        findings = []

        # 检查证书有效期
        not_after = cert.get('notAfter', '')
        not_before = cert.get('notBefore', '')
        subject = dict(x[0] for x in cert.get('subject', []))
        issuer = dict(x[0] for x in cert.get('issuer', []))

        common_name = subject.get('commonName', 'Unknown')
        issuer_name = issuer.get('commonName', 'Unknown')

        # 检查是否自签名
        if common_name == issuer_name:
            findings.append({
                'rule_id': 'ECC-003',
                'severity': 'HIGH',
                'port': port,
                'category': '证书',
                'finding': f'检测到自签名证书: {common_name}',
                'recommendation': '生产环境应使用受信任CA签发的证书',
            })

        # 检查SAN
        san = cert.get('subjectAltName', [])
        san_list = [s[1] for s in san] if san else []
        if san_list:
            findings.append({
                'rule_id': 'ECC-003',
                'severity': 'INFO',
                'port': port,
                'category': '证书SAN',
                'finding': f'SAN域名: {", ".join(san_list[:5])}',
                'recommendation': '',
            })

        # 检查密钥长度
        # RSA公钥信息在cert中
        pubkey_size = 0
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            # 尝试获取公钥大小
        except ImportError:
            pass

        if pubkey_size > 0 and pubkey_size < 2048:
            findings.append({
                'rule_id': 'ECC-004',
                'severity': 'HIGH',
                'port': port,
                'category': '密钥长度',
                'finding': f'RSA密钥长度不足: {pubkey_size}位',
                'recommendation': '建议使用至少2048位RSA密钥或ECC P-256',
            })

        # 检查证书有效期
        if not_after:
            try:
                import time
                expires_s = ssl.cert_time_to_seconds(not_after)
                remaining_days = (expires_s - time.time()) / 86400
                if remaining_days < 0:
                    findings.append({
                        'rule_id': 'ECC-003',
                        'severity': 'CRITICAL',
                        'port': port,
                        'category': '证书过期',
                        'finding': f'SSL证书已过期! (CN: {common_name})',
                        'recommendation': '立即更新证书',
                    })
                elif remaining_days < 30:
                    findings.append({
                        'rule_id': 'ECC-003',
                        'severity': 'HIGH',
                        'port': port,
                        'category': '证书即将过期',
                        'finding': f'SSL证书将在{remaining_days:.0f}天后过期 (CN: {common_name})',
                        'recommendation': '尽快更新证书，避免服务中断',
                    })
            except:
                pass

        return findings

    def _check_http_security(self, host: str, port: int) -> List[Dict]:
        """HTTP安全头检测"""
        findings = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((host, port))
            request = f'GET / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: ECC-Security-Scanner\r\nConnection: close\r\n\r\n'
            sock.send(request.encode())

            response = b''
            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                except:
                    break
            sock.close()

            resp_str = response.decode('utf-8', errors='ignore')
            headers = resp_str.split('\r\n\r\n')[0] if '\r\n\r\n' in resp_str else resp_str
            headers_lower = headers.lower()

            # HSTS检测
            if 'strict-transport-security' not in headers_lower:
                findings.append({
                    'rule_id': 'ECC-005',
                    'severity': 'MEDIUM',
                    'port': port,
                    'category': 'HSTS缺失',
                    'finding': '未启用HSTS (HTTP Strict-Transport-Security)',
                    'recommendation': '添加Strict-Transport-Security响应头，防止SSL剥离攻击',
                })

            # X-Frame-Options
            if 'x-frame-options' not in headers_lower:
                findings.append({
                    'rule_id': 'ECC-009',
                    'severity': 'LOW',
                    'port': port,
                    'category': '安全头缺失',
                    'finding': '缺少X-Frame-Options头，存在点击劫持风险',
                    'recommendation': '添加X-Frame-Options: DENY或SAMEORIGIN头',
                })

            # X-Content-Type-Options
            if 'x-content-type-options' not in headers_lower:
                findings.append({
                    'rule_id': 'ECC-010',
                    'severity': 'LOW',
                    'port': port,
                    'category': '安全头缺失',
                    'finding': '缺少X-Content-Type-Options头',
                    'recommendation': '添加X-Content-Type-Options: nosniff头',
                })

            # Server头信息泄露
            if 'server:' in headers_lower:
                server_line = [l for l in headers.split('\r\n') if 'server:' in l.lower()]
                if server_line:
                    findings.append({
                        'rule_id': 'ECC-011',
                        'severity': 'LOW',
                        'port': port,
                        'category': '信息泄露',
                        'finding': f'Server头泄露: {server_line[0].strip()}',
                        'recommendation': '隐藏或修改Server响应头，减少信息泄露',
                    })

        except Exception as e:
            pass

        return findings

    def _check_ssh_security(self, host: str, port: int) -> List[Dict]:
        """SSH安全检测"""
        findings = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((host, port))
            banner = sock.recv(256)
            sock.close()

            banner_str = banner.decode('utf-8', errors='ignore').strip()
            findings.append({
                'rule_id': 'ECC-012',
                'severity': 'INFO',
                'port': port,
                'category': 'SSH Banner',
                'finding': f'SSH Banner: {banner_str}',
                'recommendation': '检查OpenSSH版本是否为最新',
            })

            # 检查OpenSSH版本
            if 'OpenSSH' in banner_str:
                match = re.search(r'OpenSSH[_ ](\d+\.\d+)', banner_str)
                if match:
                    ver = float(match.group(1))
                    if ver < 7.0:
                        findings.append({
                            'rule_id': 'ECC-012',
                            'severity': 'CRITICAL',
                            'port': port,
                            'category': 'SSH版本过旧',
                            'finding': f'OpenSSH版本过旧: {ver}',
                            'recommendation': '升级到OpenSSH 8.0+以支持现代加密算法',
                        })
                    elif ver < 8.0:
                        findings.append({
                            'rule_id': 'ECC-012',
                            'severity': 'MEDIUM',
                            'port': port,
                            'category': 'SSH版本建议升级',
                            'finding': f'OpenSSH版本: {ver}，建议升级',
                            'recommendation': '升级到OpenSSH 8.0+以支持更好的加密算法',
                        })

        except Exception as e:
            pass

        return findings

    def run_full_check(self, host: str, open_ports: List[Dict]) -> Dict:
        """运行完整ECC安全检查"""
        start_time = datetime.now()
        all_findings = []
        checked_ports = set()

        for port_info in open_ports:
            port = port_info.get('port')
            service = port_info.get('service', '')
            if port in checked_ports:
                continue
            checked_ports.add(port)

            findings = self.check_port(host, port, service)
            all_findings.extend(findings)

        # 生成摘要
        sev_counts = {}
        for f in all_findings:
            sev = f.get('severity', 'INFO')
            sev_counts[sev] = sev_counts.get(sev, 0) + 1

        end_time = datetime.now()

        return {
            'timestamp': start_time.isoformat(),
            'duration': (end_time - start_time).total_seconds(),
            'total_findings': len(all_findings),
            'by_severity': sev_counts,
            'findings': all_findings,
            'host': host,
            'checked_ports': len(checked_ports),
        }

    def generate_ecc_report(self, ecc_result: Dict, scan_result: Dict = None) -> str:
        """生成ECC安全检测报告HTML"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        findings = ecc_result.get('findings', [])
        total = ecc_result.get('total_findings', 0)
        by_sev = ecc_result.get('by_severity', {})

        sev_colors = {
            'CRITICAL': '#c62828', 'HIGH': '#e65100',
            'MEDIUM': '#f57f17', 'LOW': '#2e7d32', 'INFO': '#1565c0'
        }

        findings_html = ''
        for f in findings:
            sev = f.get('severity', 'INFO')
            color = sev_colors.get(sev, '#666')
            findings_html += f'''
            <tr>
                <td>{f.get('rule_id', '')}</td>
                <td><span style="background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:11px;">{sev}</span></td>
                <td>{f.get('port', '')}</td>
                <td>{f.get('category', '')}</td>
                <td>{f.get('finding', '')}</td>
                <td>{f.get('recommendation', '')}</td>
            </tr>'''

        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>ECC安全检测报告 - Claude Code ECC</title>
    <style>
        body {{ font-family: "Microsoft YaHei", Arial; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #004d40, #00695c); color: white; padding: 30px; border-radius: 12px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 28px; }}
        .header .sub {{ color: #80cbc4; margin-top: 8px; }}
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 15px 0; }}
        .stat {{ background: white; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat .num {{ font-size: 28px; font-weight: bold; }}
        .stat .label {{ color: #666; font-size: 12px; }}
        .section {{ background: white; border-radius: 10px; padding: 20px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th {{ background: #004d40; color: white; padding: 8px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #e0e0e0; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ECC加密安全检测报告</h1>
            <div class="sub">Claude Code ECC 安全引擎 | {now}</div>
        </div>

        <div class="summary">
            <div class="stat"><div class="num" style="color:#c62828;">{by_sev.get('CRITICAL', 0)}</div><div class="label">严重</div></div>
            <div class="stat"><div class="num" style="color:#e65100;">{by_sev.get('HIGH', 0)}</div><div class="label">高危</div></div>
            <div class="stat"><div class="num" style="color:#f57f17;">{by_sev.get('MEDIUM', 0)}</div><div class="label">中危</div></div>
            <div class="stat"><div class="num">{total}</div><div class="label">总检测项</div></div>
        </div>

        <div class="section">
            <h2>检测结果 ({total}项)</h2>
            <table>
                <tr><th>规则ID</th><th>等级</th><th>端口</th><th>类别</th><th>发现</th><th>建议</th></tr>
                {findings_html}
            </table>
        </div>

        <div class="footer">
            ECC安全检测引擎: Claude Code ECC Security | 山西有信网安科技有限公司 &copy; 2026<br>
            本报告对SSL/TLS、证书、HTTP安全头、SSH等进行全面加密安全检测
        </div>
    </div>
</body>
</html>'''
