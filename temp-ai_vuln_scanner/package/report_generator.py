# -*- coding: utf-8 -*-
"""
AI Vuln Scanner Pro - 报告生成模块
导出漏洞扫描结果为HTML和PDF格式报告
"""
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 修复建议模板（含补丁链接）
REMEDIATION_TEMPLATES = {
    'CRITICAL': {
        'title': '紧急修复',
        'priority': 'P0',
        'description': '该漏洞已被公开利用或极易被利用，必须立即修复',
        'recommendations': [
            '立即隔离受影响系统',
            '启用紧急补丁或<a href="https://cve.mitre.org/" target="_blank">查看CVE详情</a>升级到最新版本',
            '加强网络访问控制',
            '部署入侵检测系统监控异常流量',
            '审查系统日志查找潜在入侵迹象'
        ],
        'patch_links': [
            {'name': 'NVD官方', 'url': 'https://nvd.nist.gov/vuln'},
            {'name': '厂商补丁', 'url': 'https://', 'dynamic': True}
        ]
    },
    'HIGH': {
        'title': '高优先级修复',
        'priority': 'P1',
        'description': '该漏洞可导致严重后果，建议24-48小时内修复',
        'recommendations': [
            '尽快应用<a href="https://cve.mitre.org/" target="_blank">安全补丁</a>',
            '升级到最新稳定版本',
            '限制访问来源IP',
            '启用双因素认证',
            '加强日志监控'
        ],
        'patch_links': [
            {'name': 'NVD', 'url': 'https://nvd.nist.gov/vuln'},
            {'name': 'CVE Details', 'url': 'https://www.cvedetails.com/'}
        ]
    },
    'MEDIUM': {
        'title': '中优先级修复',
        'priority': 'P2',
        'description': '该漏洞有一定风险，建议一周内修复',
        'recommendations': [
            '计划内应用<a href="https://ubuntu.com/security" target="_blank">安全更新</a>',
            '关注<a href="https://www.cnnvd.org.cn/" target="_blank">厂商安全公告</a>',
            '定期安全评估',
            '加强安全配置'
        ],
        'patch_links': [
            {'name': 'Ubuntu安全', 'url': 'https://ubuntu.com/security'},
            {'name': 'Red Hat', 'url': 'https://access.redhat.com/security'}
        ]
    },
    'LOW': {
        'title': '低优先级修复',
        'priority': 'P3',
        'description': '该漏洞风险较小，可在常规维护中修复',
        'recommendations': [
            '定期<a href="https://access.redhat.com/security" target="_blank">更新系统</a>',
            '关注安全最佳实践',
            '持续监控'
        ],
        'patch_links': [
            {'name': '厂商官网', 'url': 'https://'}
        ]
    }
}

# 常用厂商补丁链接
VENDOR_PATCH_LINKS = {
    'nginx': 'https://nginx.org/en/download.html',
    'apache': 'https://httpd.apache.org/download.cgi',
    'openssh': 'https://openssh.com/',
    'mysql': 'https://dev.mysql.com/downloads/',
    'postgresql': 'https://www.postgresql.org/download/',
    'redis': 'https://redis.io/download',
    'mongodb': 'https://www.mongodb.com/download-center',
    'iis': 'https://learn.microsoft.com/en-us/iis/',
    'windows': 'https://support.microsoft.com/help/4005551',
    'linux': 'https://linux.die.net/',
    'ubuntu': 'https://ubuntu.com/security',
    'debian': 'https://security.debian.org/',
    'centos': 'https://www.centos.org/centos-linux/',
    'redhat': 'https://access.redhat.com/security',
    'fedora': 'https://fedoraproject.org/wiki/Security',
}


class ReportGenerator:
    """报告生成器"""

    def __init__(self, output_dir: str = 'reports'):
        """初始化"""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_html_report(self, scan_data: Dict, output_filename: str = None) -> str:
        """生成HTML报告"""
        if output_filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'vuln_scan_report_{timestamp}.html'

        output_path = os.path.join(self.output_dir, output_filename)

        html_content = self._build_html(scan_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"HTML报告已生成: {output_path}")
        return output_path

    def _build_html(self, scan_data: Dict) -> str:
        """构建HTML内容"""
        # 统计数据
        statistics = scan_data.get('summary', {})
        vulnerabilities = scan_data.get('vulnerabilities', [])

        # 按严重程度分组
        by_severity = {'CRITICAL': [], 'HIGH': [], 'MEDIUM': [], 'LOW': [], 'INFO': []}
        for v in vulnerabilities:
            sev = v.get('severity', 'INFO')
            if sev not in by_severity:
                sev = 'INFO'
            by_severity[sev].append(v)

        # HTML模板
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>漏洞扫描报告 - {scan_data.get('target', 'N/A')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Microsoft YaHei', 'SimSun', sans-serif; background: #f5f7fa; color: #333; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

        /* 头部 */
        .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header .info {{ opacity: 0.8; font-size: 14px; }}

        /* 统计卡片 */
        .stats {{ display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }}
        .stat-card {{ flex: 1; min-width: 150px; background: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .stat-card.critical {{ border-left: 4px solid #ff4757; }}
        .stat-card.high {{ border-left: 4px solid #ff6b35; }}
        .stat-card.medium {{ border-left: 4px solid #ffc048; }}
        .stat-card.low {{ border-left: 4px solid #45aaf2; }}
        .stat-card .num {{ font-size: 36px; font-weight: bold; }}
        .stat-card .label {{ color: #666; font-size: 14px; }}

        /* 漏洞列表 */
        .vuln-section {{ background: white; padding: 25px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .vuln-section h2 {{ font-size: 20px; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0; }}

        .vuln-item {{ border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 15px; overflow: hidden; }}
        .vuln-item.critical {{ border-left: 4px solid #ff4757; }}
        .vuln-item.high {{ border-left: 4px solid #ff6b35; }}
        .vuln-item.medium {{ border-left: 4px solid #ffc048; }}
        .vuln-item.low {{ border-left: 4px solid #45aaf2; }}

        .vuln-header {{ background: #f8f9fa; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }}
        .vuln-title {{ font-weight: bold; font-size: 16px; }}
        .vuln-severity {{ padding: 4px 12px; border-radius: 20px; color: white; font-size: 12px; font-weight: bold; }}
        .vuln-severity.critical {{ background: #ff4757; }}
        .vuln-severity.high {{ background: #ff6b35; }}
        .vuln-severity.medium {{ background: #ffc048; }}
        .vuln-severity.low {{ background: #45aaf2; }}

        .vuln-body {{ padding: 15px 20px; }}
        .vuln-row {{ display: flex; margin-bottom: 8px; }}
        .vuln-row .label {{ color: #666; min-width: 80px; }}

        .recommendations {{ background: #fff9e6; padding: 15px; border-radius: 8px; margin-top: 10px; }}
        .recommendations h4 {{ color: #ff6b35; margin-bottom: 10px; }}
        .recommendations ul {{ margin-left: 20px; }}
        .recommendations li {{ margin-bottom: 5px; }}

        /* 补丁链接样式 */
        .patch-links {{ margin-top: 15px; padding-top: 10px; border-top: 1px dashed #ccc; }}
        .patch-links h5 {{ color: #2196F3; margin-bottom: 8px; font-size: 14px; }}
        .link-buttons {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .patch-btn {{
            display: inline-block;
            padding: 5px 12px;
            background: #4CAF50;
            color: white;
            text-decoration: none;
            border-radius: 15px;
            font-size: 12px;
            transition: background 0.3s;
        }}
        .patch-btn:hover {{ background: #45a049; }}

        /* 页脚 */
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <div class="header">
            <h1>🔒 漏洞扫描报告</h1>
            <div class="info">
                <p>扫描目标: {scan_data.get('target', 'N/A')}</p>
                <p>扫描时间: {scan_data.get('start_time', 'N/A')}</p>
                <p>扫描时长: {scan_data.get('duration', 0):.2f} 秒</p>
            </div>
        </div>

        <!-- 统计 -->
        <div class="stats">
            <div class="stat-card critical">
                <div class="num">{len(by_severity['CRITICAL'])}</div>
                <div class="label">严重 (CRITICAL)</div>
            </div>
            <div class="stat-card high">
                <div class="num">{len(by_severity['HIGH'])}</div>
                <div class="label">高危 (HIGH)</div>
            </div>
            <div class="stat-card medium">
                <div class="num">{len(by_severity['MEDIUM'])}</div>
                <div class="label">中危 (MEDIUM)</div>
            </div>
            <div class="stat-card low">
                <div class="num">{len(by_severity['LOW'])}</div>
                <div class="label">低危 (LOW)</div>
            </div>
        </div>

        <!-- 漏洞详情 -->
'''

        # 添加每个漏洞的详情
        severity_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
        for severity in severity_order:
            vulns = by_severity.get(severity, [])
            if not vulns:
                continue

            severity_info = REMEDIATION_TEMPLATES.get(severity, {})

            html += f'''
        <div class="vuln-section">
            <h2>{severity} ({len(vulns)}个)</h2>
'''

            for vuln in vulns:
                cvss = vuln.get('cvss_score', 'N/A')
                host = vuln.get('host', 'N/A')
                port = vuln.get('port', 'N/A')
                service = vuln.get('service', 'N/A')
                version = vuln.get('version', '')
                description = vuln.get('description', '无描述')

                # 生成修复建议
                remediation = self._get_recommendations(severity, service)

                html += f'''
            <div class="vuln-item {severity.lower()}">
                <div class="vuln-header">
                    <span class="vuln-title">{vuln.get('cve_id', vuln.get('vulnerability_cve', 'N/A'))}</span>
                    <span class="vuln-severity {severity.lower()}">CVSS: {cvss}</span>
                </div>
                <div class="vuln-body">
                    <div class="vuln-row"><span class="label">主机:</span> {host}:{port}</div>
                    <div class="vuln-row"><span class="label">服务:</span> {service} {version}</div>
                    <div class="vuln-row"><span class="label">描述:</span> {description}</div>
                    <div class="recommendations">
                        <h4>🔧 修复建议 ({severity_info.get('title', severity)})</h4>
                        <ul>
'''
                for rec in remediation:
                    html += f'<li>{rec}</li>'

                html += '''
                        </ul>

                        <!-- 补丁链接 -->
                        <div class="patch-links">
                            <h5>🔗 相关补丁链接:</h5>
                            <div class="link-buttons">
'''

                # 添加补丁链接
                patch_links = self._get_patch_links(service, vuln.get('cve_id'))
                for link in patch_links:
                    html += f'''<a class="patch-btn" href="{link['url']}" target="_blank">{link['name']}</a>'''

                html += '''
                            </div>
                        </div>
                    </div>
                </div>
            </div>
'''

            html += '''
        </div>
'''

        # 页脚
        html += f'''
        <div class="footer">
            <p>报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>AI Vuln Scanner Pro - 下一代智能漏洞扫描系统</p>
        </div>
    </div>
</body>
</html>
'''
        return html

    def _get_recommendations(self, severity: str, service: str) -> List[str]:
        """获取修复建议"""
        template = REMEDIATION_TEMPLATES.get(severity, REMEDIATION_TEMPLATES.get('LOW', {}))

        base_recommendations = template.get('recommendations', [])

        # 添加服务特定的建议
        service_specific = {
            'http': ['启用Web应用防火墙(WAF)', '配置HTTPS强制跳转', '启用安全响应头'],
            'https': ['启用Web应用防火墙(WAF)', '配置SSL/TLS最强加密套件', '定期更新SSL证书'],
            'ssh': ['禁用密码认证，使用密钥认证', '更改默认端口22', '配置fail2ban'],
            'ftp': ['禁用匿名访问', '使用SFTP替代FTP', '配置IP访问限制'],
            'mysql': ['限制远程访问', '使用强密码策略', '定期更换密码'],
            'redis': ['设置访问密码', '禁用危险命令', '限制绑定IP'],
            ' smb': ['禁用SMBv1', '启用签名', '限制访问共享'],
        }

        service_lower = service.lower() if service else ''
        specific = service_specific.get(service_lower, [])

        recommendations = base_recommendations + specific

        return recommendations[:6]  # 返回最多6条

    def _get_patch_links(self, service: str, cve_id: str = None) -> List[Dict]:
        """获取补丁链接"""
        links = []

        # CVE详情链接
        if cve_id:
            links.append({'name': 'CVE详情', 'url': f'https://nvd.nist.gov/vuln/detail/{cve_id}'})
            links.append({'name': 'MITRE', 'url': f'https://cve.mitre.org/cgi-bin/cvename.cgi?name={cve_id}'})
            links.append({'name': 'CNNVD', 'url': f'https://www.cnnvd.org.cn/web/vulnerability/queryLst?query={cve_id}'})

        # 服务厂商链接
        service_lower = service.lower() if service else ''
        if service_lower in VENDOR_PATCH_LINKS:
            vendor_url = VENDOR_PATCH_LINKS[service_lower]
            if vendor_url and vendor_url != 'https://':
                links.append({'name': f'{service.title()}官网', 'url': vendor_url})

        # 通用安全链接
        links.append({'name': 'NVD', 'url': 'https://nvd.nist.gov/'})
        links.append({'name': 'CVE Details', 'url': 'https://www.cvedetails.com/'})

        return links[:5]  # 最多返回5个链接

    def generate_pdf_report(self, scan_data: Dict, output_filename: str = None) -> str:
        """生成PDF报告 - 支持多种后端"""
        # 先生成HTML，再转换为PDF
        html_path = self.generate_html_report(scan_data, output_filename.replace('.pdf', '.html') if output_filename else None)
        pdf_path = html_path.replace('.html', '.pdf')

        # 尝试多种PDF生成方法，依次回退
        methods = [
            self._generate_with_weasyprint,
            self._generate_with_xhtml2pdf,
            self._generate_with_pdfkit
        ]

        for method in methods:
            try:
                result = method(html_path, pdf_path)
                if result:
                    logger.info(f"PDF报告已生成: {pdf_path} (使用 {method.__name__})")
                    return pdf_path
            except Exception:
                continue

        # 所有方法都失败，返回HTML
        logger.info("PDF依赖库未安装，已生成HTML报告（可在浏览器中打印为PDF）")
        return html_path

    def _generate_with_weasyprint(self, html_path: str, pdf_path: str) -> bool:
        """使用 WeasyPrint 生成PDF"""
        import weasyprint
        weasyprint.HTML(html_path).write_pdf(pdf_path)
        return True

    def _generate_with_xhtml2pdf(self, html_path: str, pdf_path: str) -> bool:
        """使用 xhtml2pdf (pisa) 生成PDF"""
        from xhtml2pdf import pisa
        
        with open(html_path, 'r', encoding='utf-8') as html_file:
            with open(pdf_path, 'w+b') as pdf_file:
                pisa_status = pisa.CreatePDF(html_file.read(), dest=pdf_file)
                return pisa_status.err == 0

    def _generate_with_pdfkit(self, html_path: str, pdf_path: str) -> bool:
        """使用 pdfkit (wkhtmltopdf) 生成PDF"""
        import pdfkit
        pdfkit.from_file(html_path, pdf_path)
        return True


def generate_scan_report(scan_data: Dict, output_dir: str = 'reports', formats: list = None) -> Dict[str, str]:
    """生成扫描报告

    Args:
        scan_data: 扫描数据字典
        output_dir: 输出目录
        formats: 输出格式列表 ['html', 'pdf']

    Returns:
        格式: 文件路径的字典
    """
    if formats is None:
        formats = ['html']

    generator = ReportGenerator(output_dir)

    results = {}

    if 'html' in formats:
        html_path = generator.generate_html_report(scan_data)
        results['html'] = html_path

    if 'pdf' in formats:
        try:
            pdf_path = generator.generate_pdf_report(scan_data)
            results['pdf'] = pdf_path
        except:
            pass

    return results


def export_vuln_database(db, output_path: str = 'vuln_database_export.html', limit: int = 1000) -> str:
    """导出漏洞数据库为HTML报告"""
    cves = db.search_cve(limit=limit)

    if not cves:
        logger.warning("没有漏洞数据可导出")
        return None

    scan_data = {
        'target': '漏洞数据库导出',
        'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'duration': 0,
        'vulnerabilities': [
            {
                'cve_id': cve.get('cve_id'),
                'severity': cve.get('severity'),
                'cvss_score': cve.get('cvss_score'),
                'host': cve.get('affected_products', []),
                'port': '',
                'service': '',
                'version': '',
                'description': cve.get('description', '')
            }
            for cve in cves
        ],
        'summary': {}
    }

    generator = ReportGenerator()
    html_path = generator.generate_html_report(scan_data, output_path)

    return html_path


# 测试
if __name__ == '__main__':
    test_data = {
        'target': '192.168.1.100',
        'start_time': '2026-04-30 10:00:00',
        'duration': 125.5,
        'vulnerabilities': [
            {
                'cve_id': 'CVE-2024-0001',
                'severity': 'CRITICAL',
                'cvss_score': 9.8,
                'host': '192.168.1.100',
                'port': 443,
                'service': 'nginx',
                'version': '1.24.0',
                'description': 'Nginx缓冲区溢出漏洞，允许远程代码执行'
            },
            {
                'cve_id': 'CVE-2024-0002',
                'severity': 'HIGH',
                'cvss_score': 7.5,
                'host': '192.168.1.100',
                'port': 22,
                'service': 'openssh',
                'version': '8.0',
                'description': 'OpenSSH存在拒绝服务漏洞'
            },
            {
                'cve_id': 'CVE-2024-0003',
                'severity': 'MEDIUM',
                'cvss_score': 5.0,
                'host': '192.168.1.100',
                'port': 3306,
                'service': 'mysql',
                'version': '8.0',
                'description': 'MySQL信息泄露漏洞'
            }
        ],
        'summary': {}
    }

    generator = ReportGenerator()
    html_path = generator.generate_html_report(test_data)
    print(f"HTML报告: {html_path}")