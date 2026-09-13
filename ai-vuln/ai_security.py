# -*- coding: utf-8 -*-
"""AI安全分析模块 - Claude Code Security"""
import logging
from datetime import datetime
from typing import List, Dict, Any
from html import escape as _html_escape

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AISecurityAnalyzer:
    """AI安全分析器 - 基于Claude Code Security的智能安全分析"""

    def __init__(self, db=None):
        self.db = db
        logger.info("AI安全分析器(Claude Code Security)初始化完成")

    def analyze_scan_results(self, scan_result: Dict) -> Dict:
        """AI分析扫描结果，生成深度安全洞察"""
        vulnerabilities = scan_result.get('vulnerabilities', [])
        summary = scan_result.get('summary', {})

        analysis = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'overall_risk_score': self._calculate_risk_score(vulnerabilities),
            'risk_level': '',
            'executive_summary': '',
            'key_findings': [],
            'attack_surface_analysis': '',
            'remediation_plan': [],
            'urgency_level': '',
        }

        total = summary.get('total', 0)
        high_crit = summary.get('high_critical', 0)
        by_sev = summary.get('by_severity', {})

        # 1. 风险评分 (0-100)
        risk_score = analysis['overall_risk_score']

        # 2. 风险等级
        if risk_score >= 80:
            analysis['risk_level'] = 'CRITICAL'
            analysis['urgency_level'] = '立即处置'
        elif risk_score >= 60:
            analysis['risk_level'] = 'HIGH'
            analysis['urgency_level'] = '24小时内处置'
        elif risk_score >= 40:
            analysis['risk_level'] = 'MEDIUM'
            analysis['urgency_level'] = '72小时内处置'
        elif risk_score >= 20:
            analysis['risk_level'] = 'LOW'
            analysis['urgency_level'] = '下次维护窗口处置'
        else:
            analysis['risk_level'] = 'INFO'
            analysis['urgency_level'] = '持续监控'

        # 3. 执行摘要
        if total == 0:
            analysis['executive_summary'] = '未发现安全风险，目标系统当前处于安全状态。建议保持定期扫描。'
        elif high_crit == 0:
            analysis['executive_summary'] = f'发现{total}个低风险项目，无高危漏洞。目标系统基本安全，建议按计划修复。'
        elif high_crit <= 5:
            analysis['executive_summary'] = f'发现{total}个安全项目，其中{high_crit}个高危/严重漏洞需要紧急处理。攻击面中等，建议优先修复高危漏洞。'
        else:
            analysis['executive_summary'] = f'[紧急] 发现{total}个安全项目，{high_crit}个高危/严重漏洞！攻击面较大，建议立即启动应急响应流程。'

        # 4. 关键发现
        analysis['key_findings'] = self._generate_findings(vulnerabilities, by_sev)

        # 5. 攻击面分析
        analysis['attack_surface_analysis'] = self._analyze_attack_surface(vulnerabilities)

        # 6. 修复计划
        analysis['remediation_plan'] = self._generate_remediation_plan(vulnerabilities)

        # 7. 服务分布分析
        services = {}
        for v in vulnerabilities:
            svc = v.get('service', 'unknown')
            if svc not in services:
                services[svc] = {'count': 0, 'critical': 0, 'ports': set()}
            services[svc]['count'] += 1
            if v.get('severity') in ('CRITICAL', 'HIGH'):
                services[svc]['critical'] += 1
            services[svc]['ports'].add(v.get('port'))
        analysis['service_analysis'] = services

        return analysis

    def _calculate_risk_score(self, vulnerabilities: List[Dict]) -> int:
        """计算综合风险评分 (0-100)"""
        if not vulnerabilities:
            return 0

        score = 0
        sev_weights = {'CRITICAL': 30, 'HIGH': 20, 'MEDIUM': 10, 'LOW': 3, 'INFO': 1, 'UNKNOWN': 5}
        cvss_contribution = 0

        for v in vulnerabilities:
            sev = v.get('severity', 'INFO')
            score += sev_weights.get(sev, 1)

            cvss = v.get('cvss_score') or 0
            if cvss >= 9.0:
                cvss_contribution += 5
            elif cvss >= 7.0:
                cvss_contribution += 3
            elif cvss >= 5.0:
                cvss_contribution += 1

        # Cap at 100
        return min(score + cvss_contribution, 100)

    def _generate_findings(self, vulnerabilities: List[Dict],
                          by_sev: Dict) -> List[str]:
        """生成关键发现"""
        findings = []

        critical = by_sev.get('CRITICAL', 0)
        high = by_sev.get('HIGH', 0)
        medium = by_sev.get('MEDIUM', 0)

        if critical > 0:
            findings.append(
                f'发现{critical}个严重(CRITICAL)级别漏洞，这些漏洞可能导致系统完全被攻陷，需立即修复。'
            )

        if high > 0:
            findings.append(
                f'发现{high}个高危(HIGH)级别漏洞，攻击者可能利用这些漏洞获取系统访问权限或敏感数据。'
            )

        # 检查是否有在野利用的漏洞(KEV)
        kev_count = sum(1 for v in vulnerabilities if v.get('kev'))
        if kev_count > 0:
            findings.append(
                f'[紧急] 发现{kev_count}个已被在野利用的漏洞(CISA KEV)，这些漏洞正在被攻击者活跃利用！'
            )

        # EPSS 高分（>0.9）作为第二判据，扩大在野利用识别覆盖
        epss_high_count = sum(1 for v in vulnerabilities if v.get('epss_high'))
        if epss_high_count > 0:
            findings.append(
                f'[紧急] 发现{epss_high_count}个EPSS利用概率>0.9的高危漏洞，极可能被攻击者利用，需立即处置。'
            )

        # 已知勒索软件利用（known_ransomware）最高优先级警示
        ransomware_count = sum(1 for v in vulnerabilities if v.get('known_ransomware'))
        if ransomware_count > 0:
            findings.append(
                f'[最高优先级] 发现{ransomware_count}个已知勒索软件利用漏洞(known_ransomware)，请立即隔离并处置！'
            )

        # 检查CVSS 10.0
        cvss10 = [v for v in vulnerabilities if (v.get('cvss_score') or 0) >= 10.0]
        if cvss10:
            cve_ids = ', '.join(v.get('cve_id', 'N/A') for v in cvss10[:3])
            findings.append(
                f'发现CVSS满分(10.0)漏洞: {cve_ids}，这些漏洞极其危险，修复优先级最高。'
            )

        # 开放端口统计
        ports = set(v.get('port') for v in vulnerabilities if v.get('port'))
        findings.append(
            f'共发现{len(ports)}个开放端口存在安全风险，涉及的服务包括: '
            + ', '.join(sorted(set(v.get('service', '') for v in vulnerabilities if v.get('service')))[:5])
        )

        # 服务风险
        if medium > 0:
            findings.append(
                f'发现{medium}个中危(MEDIUM)级别漏洞，建议在72小时内修复以降低攻击面。'
            )

        return findings

    def _analyze_attack_surface(self, vulnerabilities: List[Dict]) -> str:
        """分析攻击面"""
        ports = list(set(v.get('port') for v in vulnerabilities if v.get('port')))
        services = list(set(v.get('service', '') for v in vulnerabilities if v.get('service')))
        protocols = list(set(v.get('protocol', '') for v in vulnerabilities))

        high_risk_ports = set()
        for v in vulnerabilities:
            if v.get('severity') in ('CRITICAL', 'HIGH'):
                high_risk_ports.add(v.get('port'))

        parts = []
        parts.append(f'攻击面由{len(ports)}个开放端口组成。')
        parts.append(f'运行服务: {", ".join(services[:8])}。')

        if high_risk_ports:
            parts.append(
                f'高危端口({len(high_risk_ports)}个): {", ".join(str(p) for p in sorted(high_risk_ports)[:5])}'
            )

        # 高风险服务判断
        risky_services = {
            'rdp': '3389端口(RDP)暴露可能被暴力破解',
            'smb': '445端口(SMB)易受勒索软件攻击',
            'mysql': '3306端口(MySQL)数据库暴露风险',
            'redis': '6379端口(Redis)未授权访问风险',
            'mongodb': '27017端口(MongoDB)未授权访问风险',
            'telnet': '23端口(Telnet)明文传输风险',
            'ftp': '21端口(FTP)明文传输风险',
        }
        for svc, risk_desc in risky_services.items():
            if svc in services:
                parts.append(f'[风险] {risk_desc}')

        return ' '.join(parts)

    def _generate_remediation_plan(self, vulnerabilities: List[Dict]) -> List[Dict]:
        """生成修复计划"""
        plan = []

        # 按严重度排序
        sev_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3, 'INFO': 4, 'UNKNOWN': 3}
        sorted_vulns = sorted(
            vulnerabilities,
            key=lambda x: (sev_order.get(x.get('severity', 'INFO'), 5),
                          -(x.get('cvss_score') or 0))
        )

        immediate = []
        short_term = []
        medium_term = []

        for v in sorted_vulns:
            item = {
                'cve_id': v.get('cve_id', 'N/A'),
                'port': v.get('port'),
                'service': v.get('service', ''),
                'severity': v.get('severity', 'INFO'),
                'cvss': v.get('cvss_score'),
                'action': self._get_remediation_action(v),
            }
            if v.get('severity') in ('CRITICAL', 'HIGH') or v.get('kev'):
                immediate.append(item)
            elif v.get('severity') == 'MEDIUM':
                short_term.append(item)
            else:
                medium_term.append(item)

        if immediate:
            plan.append({
                'phase': '紧急处置 (立即)',
                'timeframe': '0-24小时',
                'items': immediate[:10],
                'description': '这些漏洞风险最高，建议立即采取措施。对于KEV标记的漏洞，应在CISA规定的截止日期前完成修复。'
            })

        if short_term:
            plan.append({
                'phase': '短期修复 (本周)',
                'timeframe': '1-7天',
                'items': short_term[:10],
                'description': '中危漏洞建议在72小时内修复，降低被利用的可能性。'
            })

        if medium_term:
            plan.append({
                'phase': '中期加固 (本月)',
                'timeframe': '7-30天',
                'items': medium_term[:10],
                'description': '低风险项目可安排在下次维护窗口修复。实施纵深防御策略，减少攻击面。'
            })

        return plan

    def _get_remediation_action(self, vuln: Dict) -> str:
        """根据漏洞类型生成修复建议"""
        service = (vuln.get('service', '') or '').lower()
        port = vuln.get('port')
        cve_id = vuln.get('cve_id', '')

        actions = {
            'http': '升级Web服务器到最新版本，检查HTTP安全头配置',
            'https': '升级SSL/TLS库，禁用弱加密套件，启用HSTS',
            'ssh': '升级OpenSSH到最新版本，禁用弱加密算法和过时协议',
            'smb': '禁用SMBv1，启用SMB签名和加密',
            'rdp': '启用网络级别身份验证(NLA)，限制RDP访问来源IP',
            'mysql': '升级MySQL到最新版本，限制远程访问，启用SSL连接',
            'mariadb': '升级MariaDB，限制远程访问',
            'postgresql': '升级PostgreSQL，配置pg_hba.conf限制访问',
            'redis': '设置requirepass认证，禁用危险命令，绑定localhost',
            'mongodb': '启用认证，禁用公网访问，使用TLS加密',
            'ftp': '迁移到SFTP/SCP，禁用明文FTP',
            'telnet': '立即禁用Telnet，迁移到SSH',
            'vnc': '启用VNC密码认证，使用SSH隧道',
            'msrpc': '限制RPC端口访问，启用防火墙规则',
        }
        for key, action in actions.items():
            if key in service:
                return action

        if cve_id and cve_id != 'N/A':
            return f'参考{cve_id}官方公告，应用安全补丁或更新到已修复版本'

        return f'审查端口{port}上{service}服务的安全配置，确保遵循最佳实践'

    def generate_ai_report_html(self, scan_result: Dict,
                               analysis: Dict) -> str:
        """生成AI分析HTML报告"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        summary = scan_result.get('summary', {})
        total = summary.get('total', 0)
        high_crit = summary.get('high_critical', 0)

        findings_html = ''.join(
            f'<li>{f}</li>' for f in analysis.get('key_findings', [])
        )

        # 0day/高危在野利用专项 — 单独成节，突出「最高优先级立即处置」清单
        zero_day_list = [v for v in scan_result.get('vulnerabilities', []) if v.get('is_0day')]
        zero_day_html = ''
        if zero_day_list:
            zero_day_rows = []
            for v in zero_day_list:
                cve_id = v.get('cve_id') or 'N/A'
                badges = []
                if v.get('known_ransomware'):
                    badges.append('<span class="badge-ransom">⛔ 已知勒索软件利用</span>')
                if v.get('kev'):
                    badges.append('<span class="badge-kev">CISA KEV 在野利用</span>')
                if v.get('epss_high'):
                    epss_val = v.get('epss_score')
                    epss_txt = f' {epss_val:.2f}' if isinstance(epss_val, (int, float)) else ''
                    badges.append(f'<span class="badge-epss">EPSS{epss_txt} 高危</span>')
                action = v.get('kev_required_action') or '立即打补丁/升级到已修复版本'
                zero_day_rows.append(
                    f'<tr><td>{_html_escape(str(cve_id))}</td>'
                    f'<td>{_html_escape(str(v.get("host", "")))}:{_html_escape(str(v.get("port", "")))}</td>'
                    f'<td>{_html_escape(str(v.get("service", "")))}</td>'
                    f'<td>{"".join(badges)}</td>'
                    f'<td>{_html_escape(str(action))}</td></tr>'
                )
            zero_day_html = f'''
        <div class="section zero-day">
            <h2>🚨 0day/在野利用专项 — 最高优先级立即处置清单</h2>
            <p class="zero-day-summary">共 {len(zero_day_list)} 项 0day/高危在野利用风险，请立即组织处置。以下漏洞正被攻击者活跃利用或具有极高利用概率。</p>
            <table>
                <tr><th>CVE</th><th>目标</th><th>服务</th><th>风险判据</th><th>处置要求</th></tr>
                {''.join(zero_day_rows)}
            </table>
        </div>'''

        plan_html = ''
        for phase in analysis.get('remediation_plan', []):
            items_html = ''
            for item in phase.get('items', []):
                items_html += (
                    f'<tr><td>{item["cve_id"]}</td>'
                    f'<td>{item["port"]}</td><td>{item["service"]}</td>'
                    f'<td><span class="badge">{item["severity"]}</span></td>'
                    f'<td>{item["cvss"] or ""}</td>'
                    f'<td>{item["action"]}</td></tr>'
                )
            plan_html += f'''
            <div class="phase">
                <h3>{phase["phase"]} — {phase["timeframe"]}</h3>
                <p>{phase["description"]}</p>
                <table><tr><th>CVE</th><th>端口</th><th>服务</th><th>等级</th><th>CVSS</th><th>修复方案</th></tr>
                {items_html}</table>
            </div>'''

        risk_color = {
            'CRITICAL': '#c62828', 'HIGH': '#e65100',
            'MEDIUM': '#f57f17', 'LOW': '#2e7d32', 'INFO': '#1565c0'
        }.get(analysis.get('risk_level', 'INFO'), '#666')

        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>AI安全分析报告 - Claude Code Security</title>
    <style>
        body {{ font-family: "Microsoft YaHei", Arial; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #1a237e, #283593); color: white; padding: 30px; border-radius: 12px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 28px; }}
        .header .sub {{ color: #90caf9; margin-top: 8px; }}
        .risk-badge {{ display: inline-block; padding: 8px 20px; border-radius: 20px; font-size: 18px; font-weight: bold; margin: 15px 0; }}
        .section {{ background: white; border-radius: 10px; padding: 20px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .section h2 {{ color: #1a237e; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }}
        .section ul {{ line-height: 1.8; }}
        .phase {{ background: #fafafa; border-left: 4px solid #1a237e; padding: 15px; margin: 10px 0; }}
        .phase h3 {{ margin: 0 0 5px 0; color: #1a237e; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th {{ background: #1a237e; color: white; padding: 8px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #e0e0e0; }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; background: #e0e0e0; }}
        .zero-day {{ border: 2px solid #b71c1c; background: #fff5f5; }}
        .zero-day h2 {{ color: #b71c1c; border-bottom: 2px solid #b71c1c; }}
        .zero-day-summary {{ color: #b71c1c; font-weight: bold; margin: 5px 0 12px; }}
        .badge-kev {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; background: #d32f2f; color: white; margin: 1px; }}
        .badge-ransom {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; background: #7b0000; color: white; font-weight: bold; margin: 1px; }}
        .badge-epss {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; background: #c62828; color: white; margin: 1px; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI安全分析报告</h1>
            <div class="sub">Claude Code Security 智能分析 | {now}</div>
            <div class="risk-badge" style="background:{risk_color};color:white;">
                风险等级: {analysis.get('risk_level', 'N/A')} | 综合评分: {analysis.get('overall_risk_score', 0)}/100
            </div>
            <p style="font-size:16px;">{analysis.get('executive_summary', '')}</p>
        </div>

        {zero_day_html}

        <div class="section">
            <h2>攻击面分析</h2>
            <p>{analysis.get('attack_surface_analysis', '')}</p>
        </div>

        <div class="section">
            <h2>关键发现</h2>
            <ul>{findings_html}</ul>
        </div>

        <div class="section">
            <h2>修复计划 - {analysis.get('urgency_level', '')}</h2>
            {plan_html}
        </div>

        <div class="section">
            <h2>服务风险分布</h2>
            <table>
                <tr><th>服务</th><th>漏洞数</th><th>高危数</th><th>涉及端口</th></tr>
                {''.join(
                    f'<tr><td>{svc}</td><td>{info["count"]}</td><td>{info["critical"]}</td><td>{", ".join(str(p) for p in sorted(info["ports"]))}</td></tr>'
                    for svc, info in (analysis.get('service_analysis', {}) or {}).items()
                )}
            </table>
        </div>

        <div class="footer">
            AI安全分析引擎: Claude Code Security | 山西有信网安科技有限公司 &copy; 2026<br>
            本报告由AI自动生成，仅供参考。部署前请验证修复方案的有效性。
        </div>
    </div>
</body>
</html>'''
