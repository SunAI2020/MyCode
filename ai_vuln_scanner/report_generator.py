# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 报告生成模块"""
import os
import html
from datetime import datetime
from typing import List, Dict, Optional


def generate_scan_report(scan_data: Dict, output_dir: str = 'reports',
                         formats: List[str] = None) -> Dict[str, str]:
    """生成扫描报告"""
    if formats is None:
        formats = ['html']

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_files = {}

    if 'html' in formats:
        html_path = os.path.join(output_dir, f'scan_report_{timestamp}.html')
        html_content = _generate_html_report(scan_data)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        output_files['html'] = html_path

    if 'txt' in formats:
        txt_path = os.path.join(output_dir, f'scan_report_{timestamp}.txt')
        txt_content = _generate_text_report(scan_data)
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(txt_content)
        output_files['txt'] = txt_path

    return output_files


def generate_audit_report(audit_data: Dict, output_dir: str = 'reports') -> str:
    """生成代码审计报告"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    html_path = os.path.join(output_dir, f'audit_report_{timestamp}.html')

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(_generate_audit_html(audit_data))

    return html_path


def export_vuln_database(db, output_path: str = None) -> str:
    """导出漏洞库"""
    if output_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f'vuln_database_{timestamp}.html'

    cves = db.search_cve(limit=9990000)
    cve_by_severity = db.get_cve_by_severity()

    content = _generate_vulndb_html(cves, cve_by_severity)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return output_path


def _generate_html_report(scan_data: Dict) -> str:
    """生成HTML扫描报告"""
    import html as html_module

    summary = scan_data.get('summary', {})
    vulnerabilities = scan_data.get('vulnerabilities', [])
    scan_result = scan_data.get('scan_result', {})

    rows = []
    for vuln in vulnerabilities:
        sev = (vuln.get('severity', 'INFO') or '').lower()
        row_bg = ''
        if sev in ['critical']:
            row_bg = 'background-color: #ffcdd2;'
        elif sev in ['high']:
            row_bg = 'background-color: #ffe0b2;'
        elif sev in ['medium']:
            row_bg = 'background-color: #fff9c4;'

        rows.append(f'''<tr style="{row_bg}">
            <td>{vuln.get('host', '')}</td>
            <td>{vuln.get('port', '')}</td>
            <td>{vuln.get('protocol', 'tcp')}</td>
            <td>{vuln.get('service', '')}</td>
            <td>{vuln.get('version', '')}</td>
            <td>{vuln.get('cve_id', 'N/A')}</td>
            <td><span class="badge badge-{sev}">{vuln.get('severity', 'INFO')}</span></td>
            <td>{vuln.get('cvss_score', '')}</td>
            <td>{html_module.escape((vuln.get('description', '') or '')[:120])}</td>
        </tr>''')

    host_rows = []
    for h in scan_result.get('hosts', []):
        for p in h.get('ports', []):
            host_rows.append(f'<tr><td>{h.get("ip", "")}</td><td>{p.get("port", "")}</td><td>{p.get("service", "")}</td><td>{p.get("version", "")}</td></tr>')

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>AI漏洞扫描报告</title>
    <style>
        body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 20px; background: #f0f2f5; color: #333; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 20px rgba(0,0,0,0.08); }}
        .header {{ text-align: center; padding: 20px 0; border-bottom: 3px solid #1a73e8; margin-bottom: 30px; }}
        .header h1 {{ color: #1a73e8; margin: 0; font-size: 28px; }}
        .header .subtitle {{ color: #666; margin-top: 5px; font-size: 14px; }}
        .info-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .info-item {{ display: flex; }}
        .info-label {{ font-weight: bold; color: #555; min-width: 90px; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
        .stat-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; }}
        .stat-box.critical {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        .stat-box.high {{ background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); color: #333; }}
        .stat-box.medium {{ background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); color: #333; }}
        .stat-num {{ font-size: 32px; font-weight: bold; }}
        .stat-label {{ font-size: 12px; opacity: 0.9; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 13px; }}
        th {{ background: #1a73e8; color: white; padding: 12px 10px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #f5f8ff; }}
        .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; }}
        .badge-critical {{ background: #d32f2f; color: white; }}
        .badge-high {{ background: #f57c00; color: white; }}
        .badge-medium {{ background: #fbc02d; color: #333; }}
        .badge-low {{ background: #388e3c; color: white; }}
        .badge-info {{ background: #1976d2; color: white; }}
        .section-title {{ color: #1a73e8; border-left: 4px solid #1a73e8; padding: 5px 15px; margin: 30px 0 15px; font-size: 18px; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI漏洞扫描系统 - 扫描报告</h1>
            <div class="subtitle">山西有信网安科技有限公司 | 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
        </div>

        <div class="info-grid">
            <div class="info-item"><span class="info-label">扫描目标:</span><span>{html_module.escape(scan_data.get("target", "N/A"))}</span></div>
            <div class="info-item"><span class="info-label">开始时间:</span><span>{scan_data.get("start_time", "")}</span></div>
            <div class="info-item"><span class="info-label">结束时间:</span><span>{scan_data.get("end_time", "")}</span></div>
            <div class="info-item"><span class="info-label">扫描时长:</span><span>{scan_data.get("duration", 0):.2f} 秒</span></div>
        </div>

        <div class="stats">
            <div class="stat-box"><div class="stat-num">{summary.get("total", 0)}</div><div class="stat-label">总发现</div></div>
            <div class="stat-box critical"><div class="stat-num">{summary.get("by_severity", dict()).get("CRITICAL", 0)}</div><div class="stat-label">严重</div></div>
            <div class="stat-box high"><div class="stat-num">{summary.get("high_critical", 0)}</div><div class="stat-label">高危/严重</div></div>
            <div class="stat-box medium"><div class="stat-num">{summary.get("by_severity", dict()).get("MEDIUM", 0)}</div><div class="stat-label">中危</div></div>
        </div>

        <div class="section-title">漏洞详情</div>
        <table>
            <thead><tr><th>主机</th><th>端口</th><th>协议</th><th>服务</th><th>版本</th><th>CVE</th><th>严重程度</th><th>CVSS</th><th>描述</th></tr></thead>
            <tbody>{"".join(rows) if rows else '<tr><td colspan="9" style="text-align:center;color:#999;">未发现漏洞</td></tr>'}</tbody>
        </table>

        <div class="section-title">扫描详情</div>
        <table>
            <thead><tr><th>主机</th><th>端口</th><th>服务</th><th>版本</th></tr></thead>
            <tbody>{"".join(host_rows) if host_rows else '<tr><td colspan="4" style="text-align:center;color:#999;">无扫描数据</td></tr>'}</tbody>
        </table>

        <div class="footer">本报告由AI漏洞扫描系统自动生成 | 山西有信网安科技有限公司 &copy; 2026</div>
    </div>
</body>
</html>'''


def _generate_text_report(scan_data: Dict) -> str:
    """生成文本扫描报告"""
    summary = scan_data.get('summary', {})
    vulnerabilities = scan_data.get('vulnerabilities', [])

    lines = [
        '=' * 70,
        'AI漏洞扫描系统 - 扫描报告',
        '山西有信网安科技有限公司',
        '=' * 70,
        '',
        f'扫描目标: {scan_data.get("target", "N/A")}',
        f'开始时间: {scan_data.get("start_time", "")}',
        f'结束时间: {scan_data.get("end_time", "")}',
        f'扫描时长: {scan_data.get("duration", 0):.2f} 秒',
        '',
        '-' * 70,
        '扫描摘要',
        f'  总发现: {summary.get("total", 0)} 个',
        f'  高危/严重: {summary.get("high_critical", 0)} 个',
    ]

    sev = summary.get('by_severity', {})
    for level, count in sev.items():
        lines.append(f'  {level}: {count} 个')

    lines.extend(['', '-' * 70, '漏洞详情', ''])

    for i, vuln in enumerate(vulnerabilities, 1):
        lines.extend([
            f'[{i}] {vuln.get("host", "")}:{vuln.get("port", "")}',
            f'    服务: {vuln.get("service", "")} {vuln.get("version", "")}',
            f'    CVE: {vuln.get("cve_id", "N/A")}',
            f'    严重程度: {vuln.get("severity", "INFO")} (CVSS: {vuln.get("cvss_score", "")})',
            f'    描述: {(vuln.get("description", "") or "")[:150]}',
            ''
        ])

    lines.append('=' * 70)
    return '\n'.join(lines)


def _generate_audit_html(audit_data: Dict) -> str:
    """生成代码审计HTML报告"""
    issues = audit_data.get('issues', [])
    severity_summary = audit_data.get('severity_summary', {})

    issue_rows = []
    for issue in issues:
        sev = (issue.get('severity', '') or '').lower()
        row_bg = ''
        if sev == 'critical':
            row_bg = 'background-color: #ffcdd2;'
        elif sev == 'high':
            row_bg = 'background-color: #ffe0b2;'

        issue_rows.append(f'''<tr style="{row_bg}">
            <td>{issue.get("file", "")}</td><td>{issue.get("line", "")}</td>
            <td>{issue.get("category", "")}</td>
            <td><span class="badge badge-{sev}">{issue.get("severity", "")}</span></td>
            <td><code>{html.escape(issue.get("code", "")[:80])}</code></td>
            <td>{issue.get("recommendation", "")}</td>
        </tr>''')

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>AI代码安全审计报告</title>
    <style>
        body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 20px; background: #f0f2f5; }}
        .container {{ max-width: 1300px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 20px rgba(0,0,0,0.08); }}
        .header {{ text-align: center; padding-bottom: 20px; border-bottom: 3px solid #e91e63; margin-bottom: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
        .stat-box {{ padding: 15px; border-radius: 10px; text-align: center; background: #f5f5f5; }}
        .stat-box .num {{ font-size: 28px; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th {{ background: #e91e63; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px 10px; border-bottom: 1px solid #eee; }}
        .badge {{ padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold; }}
        .badge-critical {{ background: #d32f2f; color: white; }}
        .badge-high {{ background: #f57c00; color: white; }}
        .badge-medium {{ background: #fbc02d; color: #333; }}
        .badge-low {{ background: #388e3c; color: white; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI代码安全审计报告</h1>
            <div>山西有信网安科技有限公司 | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
        </div>
        <div class="stats">
            <div class="stat-box"><div class="num">{audit_data.get("total_files_scanned", 0)}</div>扫描文件</div>
            <div class="stat-box"><div class="num">{audit_data.get("total_vulnerabilities", 0)}</div>发现问题</div>
            <div class="stat-box"><div class="num">{severity_summary.get("CRITICAL", 0)}</div>严重漏洞</div>
            <div class="stat-box"><div class="num">{severity_summary.get("HIGH", 0)}</div>高危漏洞</div>
        </div>
        <table>
            <thead><tr><th>文件</th><th>行号</th><th>类别</th><th>严重度</th><th>代码</th><th>建议</th></tr></thead>
            <tbody>{"".join(issue_rows) if issue_rows else '<tr><td colspan="6" style="text-align:center;color:#999;">未发现问题</td></tr>'}</tbody>
        </table>
        <div class="footer">本报告由AI漏洞扫描系统自动生成 | 山西有信网安科技有限公司 &copy; 2026</div>
    </div>
</body>
</html>'''


def _generate_vulndb_html(cves: List[Dict], severity_stats: Dict) -> str:
    """生成漏洞库HTML报告"""
    rows = []
    for c in cves:
        sev = (c.get('severity', 'INFO') or '').lower()
        rows.append(f'''<tr>
            <td>{c.get("cve_id", "")}</td>
            <td>{(c.get("description", "") or "")[:150]}</td>
            <td>{c.get("cvss_score", "")}</td>
            <td><span class="badge badge-{sev}">{c.get("severity", "INFO")}</span></td>
            <td>{c.get("published_date", "")}</td>
        </tr>''')

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8"><title>CVE漏洞库报告</title>
    <style>
        body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 20px; background: #f0f2f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
        .header {{ text-align: center; padding-bottom: 20px; border-bottom: 3px solid #4caf50; margin-bottom: 30px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th {{ background: #4caf50; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #eee; }}
        .badge {{ padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold; }}
        .badge-critical {{ background: #d32f2f; color: white; }}
        .badge-high {{ background: #f57c00; color: white; }}
        .badge-medium {{ background: #fbc02d; color: #333; }}
        .badge-low {{ background: #388e3c; color: white; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>CVE漏洞库报告</h1><div>山西有信网安科技有限公司 | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div></div>
        <table>
            <thead><tr><th>CVE编号</th><th>描述</th><th>CVSS</th><th>严重程度</th><th>发布日期</th></tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
        <div class="footer">山西有信网安科技有限公司 &copy; 2026</div>
    </div>
</body>
</html>'''
