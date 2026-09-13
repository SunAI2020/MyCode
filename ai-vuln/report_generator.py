# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 报告生成模块"""
import sys
import os
import html
from datetime import datetime
from urllib.parse import urlparse
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from constants import SEV_COLORS
from vuln_enrich import SERVICE_REMEDIATION, evidence_dict, remediation_dict
from audit_enrich import evidence_dict as _audit_evidence_dict, remediation_dict as _audit_remediation_dict


def generate_scan_report(scan_data: Dict, output_dir: str = 'reports',
                         formats: List[str] = None, template: str = 'standard') -> Dict[str, str]:
    """生成扫描报告（支持 5 类预定义模板：standard/compliance/high_risk/executive/technical）"""
    if formats is None:
        formats = ['html']

    # 应用报告模板：过滤/排序漏洞 + 标题 + 章节
    from report_templates import render_report
    rendered = render_report(scan_data, template)
    report_data = dict(scan_data)
    report_data['vulnerabilities'] = rendered['vulns']
    report_data['report_title'] = rendered['title']
    report_data['template'] = rendered['template']
    report_data['template_sections'] = rendered['sections']

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_files = {}

    if 'html' in formats:
        html_path = os.path.join(output_dir, f'scan_report_{timestamp}.html')
        html_content = _generate_html_report(report_data)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        output_files['html'] = html_path

    if 'txt' in formats:
        txt_path = os.path.join(output_dir, f'scan_report_{timestamp}.txt')
        txt_content = _generate_text_report(report_data)
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


_SEV_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']


def generate_web_scan_report(result: Dict, output_dir: str = 'reports') -> str:
    """生成 Web 应用安全扫描报告（HTML），返回文件路径。"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    html_path = os.path.join(output_dir, f'web_scan_report_{timestamp}.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(render_web_scan_html(result))
    return html_path


def render_web_scan_html(result: Dict) -> str:
    """渲染 Web 扫描结果为自包含 HTML 报告。"""
    target = html.escape(str(result.get('target', '未知')))
    findings = result.get('findings', []) or []
    ai_stats = result.get('ai_stats') or {}
    products = (result.get('fingerprint') or {}).get('products') or []
    high_risk = result.get('high_risk') or []
    directories = result.get('directories') or []
    zap = result.get('zap') or {}
    zap_alerts = zap.get('alerts') or []

    sev_count: Dict[str, int] = {}
    for f in findings:
        s = str(f.get('severity', 'INFO')).upper()
        sev_count[s] = sev_count.get(s, 0) + 1
    chips = ''.join(
        f'<span class="chip" style="background:{SEV_COLORS.get(s, "#888")};color:#fff">{s} {sev_count[s]}</span>'
        for s in _SEV_ORDER if s in sev_count
    )

    def esc(v):
        return html.escape(str(v)) if v is not None else ''

    fp_rows = ''.join(
        f'<tr><td>{esc(p.get("product"))}</td><td>{esc(p.get("category"))}</td>'
        f'<td>{esc(p.get("version"))}</td><td>{esc(p.get("confidence"))}</td></tr>'
        for p in products
    ) or '<tr><td colspan="4" class="muted">未识别到指纹</td></tr>'

    hr_rows = ''.join(
        f'<tr><td>{esc(h.get("path"))}</td><td>{esc(h.get("title"))}</td>'
        f'<td>{esc(h.get("severity"))}</td><td>{esc(h.get("status"))}</td></tr>'
        for h in high_risk
    ) or '<tr><td colspan="4" class="muted">未发现高危敏感路径</td></tr>'

    dir_rows = ''.join(
        f'<tr><td>{esc(d.get("path"))}</td><td>{esc(d.get("type"))}</td>'
        f'<td>{esc(d.get("status"))}</td><td>{esc(d.get("severity"))}</td></tr>'
        for d in directories
    ) or '<tr><td colspan="4" class="muted">未发现目录/备份文件</td></tr>'

    zap_rows = ''.join(
        f'<tr><td>{esc(a.get("name"))}</td><td>{esc(a.get("severity"))}</td><td>{esc(a.get("url"))}</td></tr>'
        for a in zap_alerts
    )
    if zap.get('available'):
        zap_section = (f'<h2>4. OWASP ZAP 被动扫描</h2><table>'
                       f'<thead><tr><th>告警</th><th>严重度</th><th>URL</th></tr></thead>'
                       f'<tbody>{zap_rows or "<tr><td colspan=\"3\" class=\"muted\">无告警</td></tr>"}</tbody></table>')
    else:
        zap_section = '<h2>4. OWASP ZAP</h2><p class="muted">ZAP 未启用或不可达</p>'

    finding_rows = ''
    for f in findings:
        sev = str(f.get('severity', 'INFO')).upper()
        color = SEV_COLORS.get(sev, '#888')
        if f.get('excluded_reason'):
            ai = (f'<span class="tag fp">误报已排除</span>'
                  f'<div class="reason">{esc(f.get("excluded_reason"))}</div>')
        elif f.get('ai_verified'):
            conf = float(f.get('ai_confidence', 0) or 0)
            ai = f'<span class="tag ok">AI确认 {conf:.0%}</span>'
        else:
            ai = ''
        evidence = f.get('evidence', '') or f.get('detail', '')
        remediation = f.get('remediation', '') or f.get('ai_remediation', '')
        finding_rows += (
            f'<tr><td><span class="sev" style="background:{color}">{sev}</span></td>'
            f'<td><strong>{esc(f.get("title"))}</strong><div class="sub">{esc(f.get("category"))}</div></td>'
            f'<td class="wrap">{esc(f.get("url"))}</td><td>{ai}</td>'
            f'<td class="wrap">{esc(evidence)}</td><td class="wrap">{esc(remediation)}</td></tr>'
        )
    if not finding_rows:
        finding_rows = '<tr><td colspan="6" class="muted">无漏洞发现</td></tr>'

    ai_block = ''
    if ai_stats:
        ai_block = (
            f'<div class="ai-box"><strong>AI 误报核验统计：</strong>'
            f'总数 {ai_stats.get("total", 0)} · 确认 {ai_stats.get("confirmed", 0)} · '
            f'排除 {ai_stats.get("excluded", 0)} · 跳过 {ai_stats.get("skipped", 0)} · '
            f'误报率 {float(ai_stats.get("exclusion_rate", 0) or 0):.1%}</div>'
        )

    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>Web 安全扫描报告 - {target}</title>
<style>
body{{font-family:"Segoe UI","Microsoft YaHei",sans-serif;margin:0;background:#f5f7fa;color:#333;line-height:1.6}}
.container{{max-width:1080px;margin:0 auto;padding:32px 24px 64px}}
h1{{color:#1a73e8;font-size:26px;margin:0 0 8px}}
h2{{color:#1a73e8;font-size:20px;margin:28px 0 12px;border-left:4px solid #1a73e8;padding-left:10px}}
table{{width:100%;border-collapse:collapse;background:#fff;margin:10px 0;border-radius:6px;overflow:hidden}}
th,td{{border:1px solid #e0e0e0;padding:9px 12px;text-align:left;font-size:13px;vertical-align:top}}
th{{background:#eef4fd;color:#0d47a1}}
tr:nth-child(even) td{{background:#fafbfd}}
.hero{{background:linear-gradient(135deg,#1a73e8,#0d47a1);color:#fff;border-radius:10px;padding:24px 28px;margin-bottom:20px}}
.hero .meta{{opacity:.92;font-size:13px}}
.chip{{display:inline-block;padding:4px 12px;border-radius:14px;margin:0 6px 6px 0;font-size:13px;font-weight:700}}
.sev{{display:inline-block;color:#fff;padding:2px 10px;border-radius:10px;font-size:12px;font-weight:700}}
.tag{{display:inline-block;padding:2px 10px;border-radius:10px;font-size:12px;font-weight:700}}
.tag.ok{{background:#e8f5e9;color:#2e7d32}}
.tag.fp{{background:#ffebee;color:#c62828}}
.reason{{color:#c62828;font-size:12px;margin-top:4px}}
.sub{{color:#888;font-size:12px}}
.wrap{{word-break:break-all;max-width:280px}}
.muted{{color:#999;text-align:center}}
.ai-box{{background:#e3f2fd;border-left:4px solid #1a73e8;padding:12px 16px;border-radius:6px;margin:14px 0}}
footer{{margin-top:40px;padding-top:16px;border-top:1px solid #e0e0e0;color:#999;font-size:12px;text-align:center}}
</style></head><body><div class="container">
<div class="hero"><h1>Web 应用安全扫描报告</h1>
<div class="meta">目标: {target} · 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div></div>
<div>{chips}</div>
{ai_block}
<h2>1. Web 指纹识别</h2>
<table><thead><tr><th>产品</th><th>类别</th><th>版本</th><th>置信度</th></tr></thead><tbody>{fp_rows}</tbody></table>
<h2>2. 高危敏感路径</h2>
<table><thead><tr><th>路径</th><th>标题</th><th>严重度</th><th>状态码</th></tr></thead><tbody>{hr_rows}</tbody></table>
<h2>3. 目录枚举 / 备份文件</h2>
<table><thead><tr><th>路径</th><th>类型</th><th>状态码</th><th>严重度</th></tr></thead><tbody>{dir_rows}</tbody></table>
{zap_section}
<h2>5. 漏洞发现明细（{len(findings)}）</h2>
<table><thead><tr><th>严重度</th><th>标题</th><th>URL</th><th>AI判定</th><th>证据</th><th>修复建议</th></tr></thead><tbody>{finding_rows}</tbody></table>
<footer>下一代智能漏洞扫描系统 Pro · Web 安全扫描报告</footer>
</div></body></html>'''


def _generate_html_report(scan_data: Dict) -> str:
    """生成HTML扫描报告 - 包含详尽的风险分析、补丁链接"""
    import html as html_module

    summary = scan_data.get('summary', {})
    vulnerabilities = scan_data.get('vulnerabilities', [])
    scan_result = scan_data.get('scan_result', {})
    ai_enhanced = scan_data.get('ai_enhanced', False)
    ai_stats = scan_data.get('ai_stats', {})
    ai_analysis = scan_data.get('ai_analysis', {})

    report_title = scan_data.get('report_title') or '下一代智能漏洞扫描系统 Pro - 安全扫描报告'
    template_sections = scan_data.get('template_sections') or []
    sections_html = ''
    for _s in template_sections:
        sections_html += (f'<div class="risk-overview"><strong>{html_module.escape(str(_s.get("heading", "")))}</strong>'
                          f'<p>{html_module.escape(str(_s.get("body", "")))}</p></div>')

    # AI增强统计横幅
    ai_banner_html = ''
    ai_excluded_html = ''

    if ai_enhanced:
        ai_total = ai_stats.get('total', 0)
        ai_confirmed = ai_stats.get('confirmed', 0)
        ai_excluded = ai_stats.get('excluded', 0)
        ai_pre_filtered = ai_stats.get('pre_filtered', 0)
        ai_rate = ai_stats.get('exclusion_rate', 0)
        ai_verified_count = ai_stats.get('ai_verified', 0)

        pre_filter_text = f' (其中{ai_pre_filtered}个由版本预过滤快速排除)' if ai_pre_filtered else ''
        ai_banner_html = f'''
        <div style="background:#e8f5e9; border:2px solid #4caf50; border-radius:8px; padding:15px; margin:15px 0;">
            <strong style="color:#2e7d32; font-size:16px;">🤖 AI增强核验已启用 (Claude Code Security)</strong><br>
            <span style="font-size:14px;">
            扫描原始匹配: <b>{ai_total}</b> 个漏洞 →
            AI批量核验: <b>{ai_verified_count}</b> 个 |
            AI确认真实: <b style="color:#d32f2f;">{ai_confirmed}</b> 个 |
            排除误报: <b style="color:#2e7d32;">{ai_excluded}</b> 个{pre_filter_text} |
            误报排除率: <b>{ai_rate:.1%}</b>
            </span>
        </div>'''

        if ai_analysis:
            findings_html = ''.join(f'<li>{html_module.escape(str(f))}</li>' for f in ai_analysis.get('key_findings', [])[:5])
            ai_banner_html += f'''
            <div style="background:#e3f2fd; border:1px solid #2196f3; border-radius:8px; padding:15px; margin:10px 0;">
                <strong style="color:#1565c0;">📋 AI风险分析报告</strong><br>
                <span>风险评分: <b style="color:{SEV_COLORS.get(ai_analysis.get('risk_level','MEDIUM'), '#333')};">{ai_analysis.get('risk_score', '?')}/100</b> ({ai_analysis.get('risk_level', '?')})</span><br>
                <span><b>执行摘要:</b> {ai_analysis.get('executive_summary', '')}</span>
                {f'<ul style="margin:5px 0;">{findings_html}</ul>' if findings_html else ''}
            </div>'''

        # AI排除的误报列表
        ai_excluded_list = scan_data.get('ai_excluded', [])
        if ai_excluded_list:
            excluded_rows = []
            for v in ai_excluded_list:
                pre_tag = '⚡预过滤' if v.get('pre_filtered') else '🤖AI判定'
                excluded_rows.append(f'''<tr>
                    <td>{v.get('cve_id', 'N/A')}</td>
                    <td>{v.get('service', '?')}:{v.get('port', '?')}</td>
                    <td>{v.get('version', '')[:40]}</td>
                    <td>{pre_tag}</td>
                    <td>{html_module.escape((v.get('excluded_reason', '') or v.get('ai_reasoning', ''))[:150])}</td>
                </tr>''')
            ai_excluded_html = f'''
            <div style="background:#fff3e0; border:1px solid #ff9800; border-radius:8px; padding:15px; margin:15px 0;">
                <strong style="color:#e65100;">⚠ AI排除的误报漏洞 ({len(ai_excluded_list)}个)</strong>
                <p style="color:#666;font-size:13px;margin:5px 0;">以下漏洞经过AI核验判定为误报，已从报告中排除。如需恢复，请在扫描时关闭AI核验。</p>
                <table style="font-size:12px;margin-top:10px;">
                    <tr><th>CVE编号</th><th>目标</th><th>版本</th><th>排除方式</th><th>排除原因</th></tr>
                    {''.join(excluded_rows[:20])}
                </table>
                {f'<p style="color:#999;font-size:11px;text-align:center;">... 还有 {len(ai_excluded_list) - 20} 个已排除</p>' if len(ai_excluded_list) > 20 else ''}
            </div>'''


    # === 漏洞详情表格 ===
    rows = []
    for vuln in vulnerabilities:
        sev = (vuln.get('severity', 'INFO') or '').upper()
        cve_id = vuln.get('cve_id', '')
        cvss = vuln.get('cvss_score', '')
        kev = vuln.get('kev', False)

        row_bg = ''
        if sev == 'CRITICAL':
            row_bg = 'background-color: #ffcdd2;'
        elif sev == 'HIGH':
            row_bg = 'background-color: #ffe0b2;'
        elif sev == 'MEDIUM':
            row_bg = 'background-color: #fff9c4;'

        kev_badge = ' <span style="background:#d32f2f;color:white;padding:1px 6px;border-radius:4px;font-size:10px;">KEV</span>' if kev else ''
        zero_day_badge = ' <span style="background:#b71c1c;color:white;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:bold;">0day漏洞</span>' if vuln.get('is_0day') else ''
        ransomware_badge = ' <span style="background:#7b0000;color:white;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:bold;">⛔勒索软件</span>' if vuln.get('known_ransomware') else ''
        honeypot_badge = '<span style="background:#6a1b9a;color:white;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold;">🍯蜜罐</span>' if (vuln.get('finding_type') == 'honeypot' or (vuln.get('description') or '').startswith('[蜜罐告警]')) else ''

        cve_link = ''
        if cve_id and cve_id != 'N/A':
            cve_link = f'<a href="https://nvd.nist.gov/vuln/detail/{cve_id}" target="_blank" style="color:#1a73e8;text-decoration:none;">{cve_id}</a>'

        rows.append(f'''<tr style="{row_bg}">
            <td>{vuln.get('host', '')}</td>
            <td>{vuln.get('port', '')}</td>
            <td>{vuln.get('protocol', 'tcp')}</td>
            <td>{vuln.get('service', '')}</td>
            <td style="max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="{html_module.escape(vuln.get('version', '') or '')}">{html_module.escape((vuln.get('version', '') or '')[:50])}</td>
            <td>{cve_link or cve_id or 'N/A'}{kev_badge}{zero_day_badge}{ransomware_badge}</td>
            <td><span class="badge badge-{sev.lower()}">{sev}</span></td>
            <td style="font-weight:bold;color:{SEV_COLORS.get(sev, '#333')};">{cvss}</td>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="{html_module.escape((vuln.get('description', '') or '')[:300])}">{html_module.escape((vuln.get('description', '') or '')[:100])}</td>
            <td style="text-align:center;">{honeypot_badge or ''}</td>
        </tr>''')

    # === 详细风险分析卡片 ===
    risk_cards = []
    for i, vuln in enumerate(vulnerabilities):
        sev = (vuln.get('severity', 'INFO') or '').upper()
        cve_id = vuln.get('cve_id', '')
        cvss = vuln.get('cvss_score', '')
        kev = vuln.get('kev', False)
        desc = (vuln.get('description', '') or '').strip()

        # 生成风险分析
        risk_analysis = _generate_risk_analysis(vuln)

        # 生成补丁链接
        patch_links = _generate_patch_links(cve_id, vuln)

        # CVSS评级解释
        cvss_level = ''
        if cvss:
            try:
                s = float(cvss)
                if s >= 9.0: cvss_level = '严重 - 极易利用，影响极大，需立即修复'
                elif s >= 7.0: cvss_level = '高危 - 利用难度较低，可能导致严重损害'
                elif s >= 4.0: cvss_level = '中危 - 需要一定条件才能利用'
                else: cvss_level = '低危 - 影响有限，利用条件苛刻'
            except: pass

        # AI认证标记
        ai_verified = vuln.get('ai_verified', False)
        ai_confidence = vuln.get('ai_confidence', 0)
        ai_assessed_risk = vuln.get('ai_assessed_risk', '')
        ai_badge = ''
        if ai_verified and ai_confidence >= 0.7:
            ai_badge = f'<span style="background:#e8f5e9;color:#2e7d32;padding:2px 8px;border-radius:10px;font-size:10px;margin-left:4px;" title="AI核验置信度: {ai_confidence:.0%}">🤖 AI确认 ({ai_confidence:.0%})</span>'
        elif ai_verified:
            ai_badge = f'<span style="background:#fff3e0;color:#e65100;padding:2px 8px;border-radius:10px;font-size:10px;margin-left:4px;" title="AI核验置信度: {ai_confidence:.0%}">🤖 AI核验 ({ai_confidence:.0%})</span>'

        # 结构化证据与修复方案
        evidence_html = _render_evidence_html(evidence_dict(vuln))
        remediation_html = _render_remediation_html(
            remediation_dict(vuln), risk_analysis.get('remediation', ''))

        risk_cards.append(f'''
        <div class="risk-card" style="border-left: 5px solid {SEV_COLORS.get(sev, '#1976d2')};">
            <div class="risk-card-header">
                <span class="risk-card-title">#{i+1} {cve_id or '服务检测'} — {vuln.get('service', '')} 端口{vuln.get('port', '')}</span>
                <span class="badge badge-{sev.lower()}">{sev}</span>
                <span style="font-weight:bold;color:{SEV_COLORS.get(sev, '#333')};margin-left:8px;">CVSS {cvss}</span>
                {f'<span style="background:#d32f2f;color:white;padding:2px 8px;border-radius:10px;font-size:10px;margin-left:4px;">在野利用</span>' if kev else ''}
                {f'<span style="background:#b71c1c;color:white;padding:2px 8px;border-radius:10px;font-size:10px;margin-left:4px;font-weight:bold;">0day漏洞</span>' if vuln.get('is_0day') else ''}
                {f'<span style="background:#7b0000;color:white;padding:2px 8px;border-radius:10px;font-size:10px;margin-left:4px;font-weight:bold;">⛔已知勒索软件利用</span>' if vuln.get('known_ransomware') else ''}
                {ai_badge}
                {f'<span style="margin-left:6px;font-size:11px;color:#666;">AI风险重评: {ai_assessed_risk}</span>' if (ai_assessed_risk and ai_assessed_risk != sev) else ''}
            </div>
            <div class="risk-card-body">
                <div class="risk-section">
                    <h4>漏洞描述</h4>
                    <p>{html_module.escape(desc[:500])}</p>
                </div>
                {evidence_html}
                <div class="risk-section">
                    <h4>风险分析</h4>
                    <p>{risk_analysis['summary']}</p>
                    <table class="mini-table">
                        <tr><td style="width:100px;"><b>攻击向量</b></td><td>{risk_analysis.get('attack_vector', 'N/A')}</td></tr>
                        <tr><td><b>影响范围</b></td><td>{risk_analysis.get('impact', 'N/A')}</td></tr>
                        <tr><td><b>利用难度</b></td><td>{risk_analysis.get('exploit_difficulty', 'N/A')}</td></tr>
                        <tr><td><b>修复紧急度</b></td><td><span style="color:{SEV_COLORS.get(sev, '#333')};font-weight:bold;">{risk_analysis.get('urgency', 'N/A')}</span></td></tr>
                        <tr><td><b>CVSS评级</b></td><td>{cvss_level}</td></tr>
                        {f'<tr><td><b>EPSS利用概率</b></td><td>{risk_analysis.get("epss", "N/A")}</td></tr>' if risk_analysis.get('epss') else ''}
                    </table>
                </div>
                {remediation_html}
                <div class="risk-section">
                    <h4>参考链接 & 补丁地址</h4>
                    {patch_links}
                </div>
            </div>
        </div>''')

    # === 扫描端口详情 ===
    host_rows = []
    for h in scan_result.get('hosts', []):
        for p in h.get('ports', []):
            state = p.get('state', '')
            state_color = '#4caf50' if state == 'open' else '#999'
            host_rows.append(f'''<tr>
                <td>{h.get("ip", "")}</td>
                <td>{p.get("port", "")}</td>
                <td><span style="color:{state_color};font-weight:bold;">{state}</span></td>
                <td>{p.get("service", "unknown")}</td>
                <td>{html_module.escape((p.get("version", "") or p.get("product", "") or "")[:60])}</td>
            </tr>''')

    # === 风险总结 ===
    total = summary.get('total', 0)
    by_sev = summary.get('by_severity', {})
    crit = by_sev.get('CRITICAL', 0)
    high = by_sev.get('HIGH', 0)
    medium = by_sev.get('MEDIUM', 0)
    low = by_sev.get('LOW', 0)
    # 如果 total 为 0 但各等级有数据，从各等级之和重新计算
    if total == 0:
        computed_total = sum(by_sev.values())
        if computed_total > 0:
            total = computed_total
    high_crit = summary.get('high_critical', crit + high)

    # 0day/高危在野利用漏洞数量（KEV + EPSS>0.9 双判据），汇总项重点展示
    zero_day_count = scan_data.get('zero_day_count', 0) or sum(
        1 for v in vulnerabilities if v.get('is_0day'))

    if crit > 0:
        overall_risk = '极高风险'
        overall_color = '#d32f2f'
        overall_desc = f'发现{crit}个严重漏洞，系统面临迫在眉睫的安全威胁，攻击者可能已具备利用条件。建议立即启动应急响应流程。'
    elif high > 0:
        overall_risk = '高风险'
        overall_color = '#f57c00'
        overall_desc = f'发现{high}个高危漏洞，存在较大的被攻击风险。建议在24小时内完成修复。'
    elif medium > 0:
        overall_risk = '中等风险'
        overall_color = '#fbc02d'
        overall_desc = f'发现{medium}个中危漏洞，建议在72小时内修复以降低攻击面。'
    elif low > 0:
        overall_risk = '低风险'
        overall_color = '#388e3c'
        overall_desc = '仅发现低风险项目，可在下次维护窗口处理。'
    else:
        overall_risk = '安全'
        overall_color = '#1976d2'
        overall_desc = '未发现明显安全风险，目标系统当前处于良好安全状态。继续保持。'

    # 受影响的端口统计
    affected_ports = sorted(set(v.get('port') for v in vulnerabilities if v.get('port')))
    affected_services = sorted(set(v.get('service', '') for v in vulnerabilities if v.get('service')))

    # 相似度去重统计
    dedup_stats = scan_data.get('dedup_stats') or {}
    dedup_line = ''
    if dedup_stats:
        dedup_line = (
            f'<div class="info-item"><span class="info-label">相似度去重:</span>'
            f'<span>原始 {dedup_stats.get("before", 0)} → 唯一 {dedup_stats.get("unique", 0)}'
            f' (合并 {dedup_stats.get("duplicates", 0)})</span></div>'
        )

    # AI增强修复建议
    ai_remediation_html = ''
    if ai_enhanced and ai_analysis:
        ai_priorities = ai_analysis.get('remediation_priority', [])
        if ai_priorities:
            ai_remediation_html = '<p><b>AI修复优先级:</b></p><ol>'
            for p in ai_priorities[:5]:
                ai_remediation_html += f'<li><b>{html_module.escape(str(p.get("action", "")))}</b> ({html_module.escape(str(p.get("urgency", "")))}) - {html_module.escape(str(p.get("timeframe", "")))}</li>'
            ai_remediation_html += '</ol>'
        ai_overall = ai_analysis.get('overall_recommendation', '')
        if ai_overall:
            ai_remediation_html += f'<p><b>AI综合建议:</b> {html_module.escape(str(ai_overall))}</p>'

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>{report_title}</title>
    <style>
        body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 20px; background: #f0f2f5; color: #333; }}
        .container {{ max-width: 1300px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 20px rgba(0,0,0,0.08); }}
        .header {{ text-align: center; padding: 20px 0; border-bottom: 3px solid #1a73e8; margin-bottom: 30px; }}
        .header h1 {{ color: #1a73e8; margin: 0; font-size: 28px; }}
        .header .subtitle {{ color: #666; margin-top: 5px; font-size: 14px; }}
        .info-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .info-item {{ display: flex; }}
        .info-label {{ font-weight: bold; color: #555; min-width: 90px; }}
        .stats {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 15px; margin: 20px 0; }}
        .stat-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; }}
        .stat-box.critical {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        .stat-box.high {{ background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); color: #333; }}
        .stat-box.medium {{ background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); color: #333; }}
        .stat-box.low {{ background: linear-gradient(135deg, #a5d6a7 0%, #c8e6c9 100%); color: #333; }}
        .stat-box.zero-day {{ background: linear-gradient(135deg, #b71c1c 0%, #e53935 100%); }}
        .stat-num {{ font-size: 32px; font-weight: bold; }}
        .stat-label {{ font-size: 12px; opacity: 0.9; margin-top: 5px; }}
        .risk-overview {{ background: #fafafa; border-radius: 12px; padding: 25px; margin: 20px 0; border: 1px solid #e0e0e0; }}
        .risk-overview .risk-level {{ font-size: 24px; font-weight: bold; }}
        .risk-overview p {{ color: #555; line-height: 1.8; }}
        .risk-overview ul {{ color: #555; line-height: 1.8; }}
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
        .risk-card {{ background: #fafafa; margin: 15px 0; padding: 0; border-radius: 8px; overflow: hidden; }}
        .risk-card-header {{ background: white; padding: 15px 20px; border-bottom: 1px solid #e0e0e0; display: flex; align-items: center; }}
        .risk-card-title {{ font-weight: bold; font-size: 15px; flex: 1; }}
        .risk-card-body {{ padding: 20px; }}
        .risk-section {{ margin-bottom: 18px; }}
        .risk-section h4 {{ color: #1a73e8; margin: 0 0 8px 0; font-size: 14px; }}
        .risk-section p {{ color: #555; line-height: 1.7; margin: 5px 0; }}
        .mini-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        .mini-table td {{ padding: 5px 8px; border-bottom: 1px solid #f0f0f0; }}
        .mini-table tr:last-child td {{ border-bottom: none; }}
        .patch-link {{ display: inline-block; background: #e3f2fd; padding: 5px 12px; margin: 3px 5px 3px 0; border-radius: 4px; font-size: 12px; color: #1a73e8; text-decoration: none; }}
        .patch-link:hover {{ background: #bbdefb; }}
        .patch-link.kev {{ background: #ffebee; color: #d32f2f; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; }}
        a {{ color: #1a73e8; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{report_title}</h1>
            <div class="subtitle">Claude Code Security AI增强分析 | 山西有信网安科技有限公司<br>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
        </div>
        {sections_html}

        <div class="info-grid">
            <div class="info-item"><span class="info-label">扫描目标:</span><span>{html_module.escape(scan_data.get("target", "N/A"))}</span></div>
            <div class="info-item"><span class="info-label">开始时间:</span><span>{scan_data.get("start_time", "")}</span></div>
            <div class="info-item"><span class="info-label">结束时间:</span><span>{scan_data.get("end_time", "")}</span></div>
            <div class="info-item"><span class="info-label">扫描时长:</span><span>{scan_data.get("duration", 0):.2f} 秒</span></div>
            {dedup_line}
        </div>

        <div class="stats">
            <div class="stat-box"><div class="stat-num">{total}</div><div class="stat-label">总发现</div></div>
            <div class="stat-box critical"><div class="stat-num">{crit}</div><div class="stat-label">严重</div></div>
            <div class="stat-box high"><div class="stat-num">{high}</div><div class="stat-label">高危</div></div>
            <div class="stat-box medium"><div class="stat-num">{medium}</div><div class="stat-label">中危</div></div>
            <div class="stat-box low"><div class="stat-num">{low}</div><div class="stat-label">低危</div></div>
            <div class="stat-box zero-day"><div class="stat-num">{zero_day_count}</div><div class="stat-label">0day漏洞</div></div>
        </div>

        {ai_banner_html}

        {ai_excluded_html}

        <div class="risk-overview">
            <div class="risk-level" style="color:{overall_color};">综合风险评级: {overall_risk}</div>
            <p>{overall_desc}</p>
            <p><b>受影响端口:</b> {", ".join(str(p) for p in affected_ports) if affected_ports else "无"}</p>
            <p><b>受影响服务:</b> {", ".join(affected_services) if affected_services else "无"}</p>
            {ai_remediation_html}
            <p><b>修复建议:</b></p>
            <ul>
                <li>优先修复标记为"在野利用(KEV)"的漏洞，此类漏洞已被攻击者活跃利用</li>
                <li>CVSS 9.0+漏洞应立即修复，此类漏洞极易被利用且影响巨大</li>
                <li>CVSS 7.0-8.9漏洞应在24小时内完成修复</li>
                <li>参考下方补丁链接，升级到对应厂商发布的安全版本</li>
                <li>修复完成后进行验证扫描，确认漏洞已消除</li>
            </ul>
        </div>

        <div class="section-title">详细漏洞风险分析 & 补丁链接</div>
        {"".join(risk_cards) if risk_cards else '<p style="text-align:center;color:#999;">未发现安全漏洞</p>'}

        <div class="section-title">漏洞列表总览</div>
        <table>
            <thead><tr><th>主机</th><th>端口</th><th>协议</th><th>服务</th><th>版本</th><th>CVE</th><th>严重程度</th><th>CVSS</th><th>描述</th><th>蜜罐</th></tr></thead>
            <tbody>{"".join(rows) if rows else '<tr><td colspan="10" style="text-align:center;color:#999;">未发现漏洞</td></tr>'}</tbody>
        </table>

        <div class="section-title">端口扫描详情</div>
        <table>
            <thead><tr><th>主机</th><th>端口</th><th>状态</th><th>服务</th><th>版本</th></tr></thead>
            <tbody>{"".join(host_rows) if host_rows else '<tr><td colspan="5" style="text-align:center;color:#999;">无扫描数据</td></tr>'}</tbody>
        </table>

        <div class="footer">
            本报告由下一代智能漏洞扫描系统 Pro v1.0 自动生成 | Claude Code Security AI增强<br>
            山西有信网安科技有限公司 &copy; 2026 | 报告仅供参考，部署前请验证修复方案
        </div>
    </div>
</body>
</html>'''


def _safe_href(url) -> bool:
    """仅允许 http/https 作为超链接，防 javascript: 等危险 scheme 注入"""
    try:
        return urlparse(str(url)).scheme in ('http', 'https')
    except ValueError:
        return False


def _render_ref_links(refs) -> str:
    """渲染参考链接：http/https 生成锚点，其余降级为纯文本"""
    out = []
    for r in refs:
        s = str(r)
        if _safe_href(s):
            out.append(
                f'<a href="{html.escape(s)}" target="_blank" rel="noopener noreferrer">'
                f'{html.escape(s[:60])}</a>'
            )
        else:
            out.append(f'<code>{html.escape(s[:60])}</code>')
    return ' '.join(out)


def _render_evidence_html(evidence: Dict) -> str:
    """渲染结构化证据为键值表（风险卡内嵌 section）"""
    if not evidence:
        return ''
    field_map = [
        ('主机', 'host'), ('端口', 'port'), ('协议', 'protocol'),
        ('服务', 'service'), ('版本', 'version'), ('产品', 'product'),
        ('CVE', 'cve_id'), ('CVSS', 'cvss_score'), ('严重程度', 'severity'),
        ('KEV在野利用', 'kev'), ('匹配方式', 'matched_by'),
    ]
    rows = []
    for label, key in field_map:
        val = evidence.get(key)
        if val in (None, '', [], False):
            continue
        if key == 'kev':
            val = '是' if val else '否'
        rows.append(
            f'<tr><td style="width:110px;"><b>{label}</b></td>'
            f'<td>{html.escape(str(val))}</td></tr>'
        )
    refs = evidence.get('references') or []
    if refs:
        ref_html = _render_ref_links(refs)
        rows.append(f'<tr><td><b>参考链接</b></td><td>{ref_html}</td></tr>')
    summary = evidence.get('summary') or ''
    summary_html = (f'<p style="margin:0 0 8px;color:#555;">{html.escape(str(summary))}</p>'
                    if summary else '')
    return (f'<div class="risk-section"><h4>证据 (Evidence)</h4>{summary_html}'
            f'<table class="mini-table">{"".join(rows)}</table></div>')


def _render_remediation_html(remediation: Dict, fallback: str = '') -> str:
    """渲染结构化修复方案：编号步骤 + 来源徽标 + 紧急度 + 参考链接"""
    if not remediation:
        return f'<div class="risk-section"><h4>修复方案</h4><p>{html.escape(fallback)}</p></div>' if fallback else ''
    source = remediation.get('source') or 'generic'
    source_label = {'ai': 'AI', 'rule': '规则库', 'generic': '通用'}.get(source, source)
    source_color = {'ai': '#2e7d32', 'rule': '#1565c0', 'generic': '#6a1b9a'}.get(source, '#666')
    badge = (f'<span style="background:{source_color};color:#fff;padding:1px 8px;'
             f'border-radius:10px;font-size:11px;margin-left:6px;">{source_label}</span>')
    parts = []
    summary = remediation.get('summary') or ''
    if summary:
        parts.append(f'<p style="margin:0 0 6px;color:#555;">{html.escape(str(summary))}</p>')
    steps = remediation.get('steps') or []
    if steps:
        items = ''.join(f'<li>{html.escape(str(s))}</li>' for s in steps)
        parts.append(f'<ol style="margin:6px 0 6px 18px;padding:0;">{items}</ol>')
    urgency = remediation.get('urgency') or ''
    if urgency:
        parts.append(f'<p style="margin:4px 0;font-weight:bold;color:#d32f2f;">修复紧急度: {html.escape(str(urgency))}</p>')
    refs = remediation.get('references') or []
    if refs:
        ref_html = _render_ref_links(refs)
        parts.append(f'<p style="margin:4px 0;">参考: {ref_html}</p>')
    return f'<div class="risk-section"><h4>修复方案 {badge}</h4>{"".join(parts)}</div>'


def _generate_risk_analysis(vuln: Dict) -> Dict[str, str]:
    """生成单个漏洞的风险分析"""
    cve_id = vuln.get('cve_id', '')
    cvss = vuln.get('cvss_score', '')
    sev = (vuln.get('severity', 'INFO') or '').upper()
    service = (vuln.get('service', '') or '').lower()
    desc = (vuln.get('description', '') or '').lower()
    kev = vuln.get('kev', False)

    analysis = {
        'summary': '',
        'attack_vector': '网络远程',
        'impact': '待评估',
        'exploit_difficulty': '待评估',
        'urgency': '待评估',
        'remediation': '',
        'epss': '',
    }

    # 攻击向量判断
    if cvss:
        try:
            s = float(cvss)
            if s >= 9.0:
                analysis['exploit_difficulty'] = '极低 - 可自动化利用'
                analysis['urgency'] = '立即修复 (0-4小时)'
            elif s >= 7.0:
                analysis['exploit_difficulty'] = '较低 - PoC可能已公开'
                analysis['urgency'] = '紧急修复 (24小时内)'
            elif s >= 4.0:
                analysis['exploit_difficulty'] = '中等 - 需一定技术能力'
                analysis['urgency'] = '计划修复 (72小时内)'
            else:
                analysis['exploit_difficulty'] = '较高 - 需特定条件'
                analysis['urgency'] = '排期修复 (30天内)'
        except:
            pass

    if kev:
        analysis['exploit_difficulty'] = '已在野利用 - 极度紧急'
        analysis['urgency'] = '立即修复! (CISA KEV)'

    if vuln.get('known_ransomware'):
        analysis['exploit_difficulty'] = '已知勒索软件利用 - 最高优先级'
        analysis['urgency'] = '立即处置! (勒索软件)'
    elif vuln.get('epss_high'):
        analysis['exploit_difficulty'] = '高利用概率 - 极可能被攻击'
        analysis['urgency'] = '立即修复! (EPSS高危)'

    if vuln.get('epss_score') is not None:
        analysis['epss'] = f"{vuln.get('epss_score'):.2%}"

    # 服务相关风险描述
    service_risks = {
        'smb': {'attack_vector': '网络(SMB协议)', 'impact': '可导致远程代码执行、文件泄露、勒索软件传播'},
        'msrpc': {'attack_vector': '网络(RPC协议)', 'impact': '可导致权限提升、远程命令执行'},
        'microsoft-ds': {'attack_vector': '网络(SMB/CIFS)', 'impact': '可导致文件共享泄露、远程代码执行'},
        'http': {'attack_vector': '网络(HTTP)', 'impact': '可导致信息泄露、XSS、SQL注入、远程代码执行'},
        'https': {'attack_vector': '网络(HTTPS/TLS)', 'impact': '可导致中间人攻击、敏感数据泄露'},
        'ssh': {'attack_vector': '网络(SSH)', 'impact': '可导致未授权访问、暴力破解、权限提升'},
        'rdp': {'attack_vector': '网络(RDP)', 'impact': '可导致远程桌面劫持、凭据窃取'},
        'mysql': {'attack_vector': '网络(数据库)', 'impact': '可导致数据泄露、SQL注入、权限提升'},
        'redis': {'attack_vector': '网络(缓存)', 'impact': '可导致未授权访问、数据篡改、服务器控制'},
    }
    if service in service_risks:
        analysis['attack_vector'] = service_risks[service]['attack_vector']
        analysis['impact'] = service_risks[service]['impact']
    elif 'inject' in desc or 'overflow' in desc or 'rce' in desc:
        analysis['impact'] = '可导致远程代码执行、系统完全被控制'

    # 修复建议（复用 vuln_enrich.SERVICE_REMEDIATION 集中映射）
    if service in SERVICE_REMEDIATION:
        steps = SERVICE_REMEDIATION[service]
        analysis['remediation'] = '\n'.join(f'{i}. {s}' for i, s in enumerate(steps, 1))
    else:
        analysis['remediation'] = (f'1. 参考{cve_id}官方公告获取补丁\n2. 升级受影响的软件到安全版本\n'
                                   f'3. 实施最小权限原则\n4. 配置防火墙限制暴露面')

    # 描述分析
    if 'remote code' in desc or 'rce' in desc:
        analysis['summary'] = '此漏洞允许攻击者远程执行任意代码，可能导致服务器完全被控制。'
    elif 'privilege escalation' in desc or '权限提升' in desc:
        analysis['summary'] = '此漏洞允许攻击者提升权限，从低权限用户获取系统管理员权限。'
    elif 'denial of service' in desc or 'dos' in desc:
        analysis['summary'] = '此漏洞可导致服务拒绝，影响系统可用性。'
    elif 'information disclosure' in desc or '信息泄露' in desc:
        analysis['summary'] = '此漏洞可导致敏感信息泄露，包括配置文件、凭据等。'
    elif 'injection' in desc or '注入' in desc:
        analysis['summary'] = '此漏洞允许攻击者注入恶意代码或命令，可导致代码执行、数据窃取等。'
    elif 'overflow' in desc or '溢出' in desc:
        analysis['summary'] = '此漏洞为缓冲区溢出类型，可能导致程序崩溃或远程代码执行。'
    elif 'bypass' in desc or '绕过' in desc:
        analysis['summary'] = '此漏洞允许绕过安全限制，访问受保护的资源或功能。'
    else:
        analysis['summary'] = f'此{sev}级别漏洞影响{service}服务，CVSS评分{cvss}，建议优先修复。'

    return analysis


def _generate_patch_links(cve_id: str, vuln: Dict = None) -> str:
    """生成补丁和参考链接HTML"""
    links = []

    if cve_id and cve_id != 'N/A':
        # NVD详情页
        links.append(f'<a class="patch-link" href="https://nvd.nist.gov/vuln/detail/{cve_id}" target="_blank">NVD漏洞详情</a>')

        # MITRE CVE
        links.append(f'<a class="patch-link" href="https://cve.mitre.org/cgi-bin/cvename.cgi?name={cve_id}" target="_blank">MITRE CVE</a>')

        # CVE Details
        links.append(f'<a class="patch-link" href="https://www.cvedetails.com/cve/{cve_id}/" target="_blank">CVE Details</a>')

        # CISA KEV
        if vuln and vuln.get('kev'):
            links.append(f'<a class="patch-link kev" href="https://www.cisa.gov/known-exploited-vulnerabilities-catalog" target="_blank">CISA KEV (在野利用)</a>')

        # NVD API
        links.append(f'<a class="patch-link" href="https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}" target="_blank">NVD API JSON</a>')

        # EPSS
        links.append(f'<a class="patch-link" href="https://api.first.org/data/v1/epss?cve={cve_id}" target="_blank">EPSS利用预测</a>')

    # 服务相关链接
    if vuln:
        service = (vuln.get('service', '') or '').lower()
        product = (vuln.get('version', '') or '').lower()
        port = vuln.get('port')

        vendor_links = {
            'smb': ['https://www.samba.org/samba/security/', 'https://msrc.microsoft.com/update-guide/'],
            'msrpc': ['https://msrc.microsoft.com/update-guide/'],
            'microsoft-ds': ['https://msrc.microsoft.com/update-guide/'],
            'rdp': ['https://msrc.microsoft.com/update-guide/'],
            'http': ['https://httpd.apache.org/security/', 'https://nginx.org/en/security_advisories.html'],
            'ssh': ['https://www.openssh.com/security.html'],
            'mysql': ['https://dev.mysql.com/doc/relnotes/mysql/8.0/en/', 'https://mariadb.org/security/'],
            'redis': ['https://redis.io/security/'],
            'postgresql': ['https://www.postgresql.org/support/security/'],
            'mongodb': ['https://www.mongodb.com/alerts'],
            'ftp': ['https://security.appspot.com/vsftpd.html'],
            'telnet': ['https://nvd.nist.gov/vuln/search'],
        }

        for key, urls in vendor_links.items():
            if key in service or key in product:
                for url in urls:
                    label = url.split('//')[1].split('/')[0] if '//' in url else url
                    links.append(f'<a class="patch-link" href="{url}" target="_blank">厂商安全公告 ({label})</a>')

    if not links:
        links.append('<span style="color:#999;">暂无补丁链接</span>')

    return '<div style="margin-top:8px;">' + '\n'.join(set(links)) + '</div>'


def _generate_text_report(scan_data: Dict) -> str:
    """生成文本扫描报告"""
    summary = scan_data.get('summary', {})
    vulnerabilities = scan_data.get('vulnerabilities', [])

    total = summary.get('total', 0)
    sev = summary.get('by_severity', {})
    # 如果 total 为 0 但各等级有数据，从各等级之和重新计算
    if total == 0:
        computed_total = sum(sev.values())
        if computed_total > 0:
            total = computed_total

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
        f'  总发现: {total} 个',
        f'  高危/严重: {summary.get("high_critical", 0)} 个',
    ]

    for level, count in sev.items():
        lines.append(f'  {level}: {count} 个')

    dedup = scan_data.get('dedup_stats')
    if dedup:
        lines.append(
            f'  去重: 原始 {dedup.get("before", 0)} → 唯一 {dedup.get("unique", 0)}'
            f' (合并 {dedup.get("duplicates", 0)})'
        )

    lines.extend(['', '-' * 70, '漏洞详情', ''])

    for i, vuln in enumerate(vulnerabilities, 1):
        ev = evidence_dict(vuln)
        rm = remediation_dict(vuln)
        evidence_line = ev.get('summary', '') if ev else ''
        remed_steps = rm.get('steps', []) if rm else []
        remed_line = '; '.join(remed_steps[:3]) if remed_steps else ''

        block = [
            f'[{i}] {vuln.get("host", "")}:{vuln.get("port", "")}',
            f'    服务: {vuln.get("service", "")} {vuln.get("version", "")}',
            f'    CVE: {vuln.get("cve_id", "N/A")}',
            f'    严重程度: {vuln.get("severity", "INFO")} (CVSS: {vuln.get("cvss_score", "")})',
            f'    描述: {(vuln.get("description", "") or "")[:150]}',
        ]
        if evidence_line:
            block.append(f'    证据: {evidence_line[:200]}')
        if remed_line:
            block.append(f'    修复方案: {remed_line[:200]}')
        block.append('')
        lines.extend(block)

    lines.append('=' * 70)
    return '\n'.join(lines)


# 质量审计维度中文名映射（与 ai_code_reviewer.QUALITY_DIMENSIONS 保持一致）
DIMENSION_LABELS = {
    'security': '安全', 'architecture': '架构设计', 'logic': '逻辑问题',
    'function': '函数规范', 'completeness': '功能完整性', 'loop': '循环与复杂度',
    'invocation': '调用关系', 'interface': '接口规范', 'parameter': '参数传递',
    'naming': '命名标识', 'io': '输入输出', 'ui': '交互界面',
    'api': 'API设计', 'database': '数据库',
}


def _render_audit_solution_html(issue: Dict) -> str:
    """渲染代码审计发现的解决方案单元格：来源徽标 + 摘要 + 步骤列表"""
    rm = _audit_remediation_dict(issue)
    source = rm.get('source') or 'generic'
    label = {'ai': 'AI', 'rule': '规则', 'generic': '通用'}.get(source, source)
    color = {'ai': '#2e7d32', 'rule': '#1565c0', 'generic': '#6a1b9a'}.get(source, '#666')
    badge = (f'<span style="background:{color};color:#fff;padding:1px 6px;border-radius:8px;'
             f'font-size:10px;margin-right:4px;">{label}</span>')
    summary = html.escape(str(rm.get('summary') or ''))
    steps = rm.get('steps') or []
    steps_html = '<br>'.join(f'{i + 1}. {html.escape(str(s))}' for i, s in enumerate(steps[:6]))
    if len(steps) > 6:
        steps_html += f'<br>… 共 {len(steps)} 步'
    urgency = rm.get('urgency') or ''
    urgency_html = (f'<br><span style="color:#d32f2f;font-size:11px;">⏱ {html.escape(str(urgency))}</span>'
                    if urgency else '')
    return f'{badge}{summary}{urgency_html}<br><small style="color:#555;">{steps_html}</small>'


def _generate_audit_html(audit_data: Dict, title: str = 'AI代码安全审计报告') -> str:
    """生成代码审计HTML报告（title 可自定义，供代码质量检测等复用）"""
    issues = audit_data.get('issues', [])
    severity_summary = audit_data.get('severity_summary', {})
    ai_enhanced = audit_data.get('ai_enhanced', False)
    dimension_summary = audit_data.get('dimension_summary', {})

    # AI验证统计信息
    ai_stats_html = ''
    if ai_enhanced:
        regex_candidates = audit_data.get('regex_candidates', 0)
        ai_excluded = audit_data.get('ai_excluded_count', 0)
        ai_confirmed = audit_data.get('ai_confirmed', 0)
        ai_stats_html = f'''
        <div style="background:#e8f5e9; border:1px solid #4caf50; border-radius:8px; padding:15px; margin:15px 0;">
            <strong style="color:#2e7d32;">🤖 AI增强验证已启用 (Claude Code Security)</strong><br>
            Regex初筛候选: <b>{regex_candidates}</b> →
            AI确认漏洞: <b style="color:#d32f2f;">{ai_confirmed}</b> |
            排除误报: <b style="color:#2e7d32;">{ai_excluded}</b>
        </div>'''

    issue_rows = []
    for issue in issues:
        sev = (issue.get('severity', '') or '').lower()
        row_bg = ''
        if sev == 'critical':
            row_bg = 'background-color: #ffcdd2;'
        elif sev == 'high':
            row_bg = 'background-color: #ffe0b2;'

        # AI验证信心度标签
        ai_badge = ''
        if issue.get('ai_verified'):
            confidence = issue.get('ai_confidence', 0)
            conf_pct = f'{confidence:.0%}'
            ai_color = '#2e7d32' if confidence >= 0.8 else '#f57c00' if confidence >= 0.6 else '#d32f2f'
            ai_badge = (f' <span style="background:{ai_color};color:white;padding:1px 6px;'
                       f'border-radius:4px;font-size:10px;">AI确认 {conf_pct}</span>')

        # AI修复建议覆盖（如果有）
        dim = issue.get('dimension') or 'security'
        dim_name = DIMENSION_LABELS.get(dim, '安全')
        problem = issue.get('problem') or issue.get('code') or ''
        ev = _audit_evidence_dict(issue)
        ev_title = html.escape(str(ev.get('summary') or '') + ' | ' + str(ev.get('code') or ''))

        issue_rows.append(f'''<tr style="{row_bg}">
            <td>{html.escape(str(issue.get("file", "")))}</td>
            <td>{issue.get("line", "")}</td>
            <td>{html.escape(dim_name)}</td>
            <td>{html.escape(str(issue.get("category", "")))}{ai_badge}</td>
            <td><span class="badge badge-{sev}">{issue.get("severity", "")}</span></td>
            <td><code>{html.escape(issue.get("code", "")[:80])}</code></td>
            <td title="{ev_title}">{html.escape(problem)}</td>
            <td>{_render_audit_solution_html(issue)}</td>
        </tr>''')

    # 维度分布统计
    dim_stats_html = ''
    if dimension_summary:
        dim_items = ' '.join(
            f'<span style="background:#f3e5f5;color:#6a1b9a;padding:3px 10px;border-radius:12px;'
            f'margin:2px;display:inline-block;font-size:12px;">'
            f'{DIMENSION_LABELS.get(k, k)}: {v}</span>'
            for k, v in dimension_summary.items()
        )
        dim_stats_html = f'''
        <div style="margin:15px 0; padding:12px; background:#fafafa; border:1px solid #e0e0e0; border-radius:8px;">
            <strong>📊 问题维度分布：</strong>{dim_items}
        </div>'''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>{html.escape(title)}</title>
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
            <h1>{html.escape(title)}</h1>
            <div>山西有信网安科技有限公司 | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
        </div>
        <div class="stats">
            <div class="stat-box"><div class="num">{audit_data.get("total_files_scanned", 0)}</div>扫描文件</div>
            <div class="stat-box"><div class="num">{audit_data.get("total_vulnerabilities", 0)}</div>发现问题</div>
            <div class="stat-box"><div class="num">{severity_summary.get("CRITICAL", 0)}</div>严重漏洞</div>
            <div class="stat-box"><div class="num">{severity_summary.get("HIGH", 0)}</div>高危漏洞</div>
        </div>
        {ai_stats_html}
        {dim_stats_html}
        <table>
            <thead><tr><th>文件</th><th>行号</th><th>维度</th><th>类别</th><th>严重度</th><th>代码</th><th>问题描述</th><th>解决方案</th></tr></thead>
            <tbody>{"".join(issue_rows) if issue_rows else '<tr><td colspan="8" style="text-align:center;color:#999;">未发现问题</td></tr>'}</tbody>
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
        cwe = (c.get('cwe', '') or '')[:30]
        patch = (c.get('patch_link', '') or '')[:80]
        patch_cell = f'<a href="{patch}" target="_blank">{patch}</a>' if patch else ''
        rows.append(f'''<tr>
            <td>{c.get("cve_id", "")}</td>
            <td>{(c.get("description", "") or "")[:150]}</td>
            <td>{c.get("cvss_score", "")}</td>
            <td><span class="badge badge-{sev}">{c.get("severity", "INFO")}</span></td>
            <td>{c.get("published_date", "")}</td>
            <td>{cwe}</td>
            <td>{patch_cell}</td>
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
            <thead><tr><th>CVE编号</th><th>描述</th><th>CVSS</th><th>严重程度</th><th>发布日期</th><th>CWE</th><th>补丁链接</th></tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
        <div class="footer">山西有信网安科技有限公司 &copy; 2026</div>
    </div>
</body>
</html>'''
