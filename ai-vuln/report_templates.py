# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 报告模板模块（5 类预定义模板）"""
import logging
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEMPLATE_DEFS = {
    'standard': {'title': '标准漏洞扫描报告', 'desc': '完整的扫描结果与风险分析'},
    'compliance': {'title': '合规检查报告（等保 2.0）', 'desc': '映射等保 2.0 条款'},
    'high_risk': {'title': '高危漏洞专报', 'desc': '仅 CRITICAL/HIGH + 修复优先级'},
    'executive': {'title': '管理简报', 'desc': '摘要 + 关键指标'},
    'technical': {'title': '技术详报', 'desc': '全字段 + EPSS/CWE/证据'},
}

_SEV_RANK = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3, 'INFO': 4}


def _filter_vulns(vulns: List[Dict], template: str) -> List[Dict]:
    if template == 'high_risk':
        return [v for v in vulns if str(v.get('severity', '')).upper() in ('CRITICAL', 'HIGH')]
    return list(vulns)


def _build_sections(scan_data: Dict, template: str) -> List[Dict]:
    summary = scan_data.get('summary', {})
    if template == 'executive':
        return [{'heading': '执行摘要',
                 'body': f"发现 {summary.get('total', 0)} 个漏洞，"
                         f"其中高危/严重 {summary.get('high_critical', 0)} 个，"
                         f"建议优先处置。"}]
    if template == 'compliance':
        return [{'heading': '等保 2.0 映射',
                 'body': '安全区域边界、安全计算环境、安全管理中心条款对照；'
                         '重点关注访问控制、安全审计、入侵防范、数据完整性。'}]
    if template == 'technical':
        return [{'heading': '技术详情',
                 'body': '含 CVSS/EPSS/CWE/证据/补丁链接完整字段，供技术团队修复定位。'}]
    if template == 'high_risk':
        return [{'heading': '高危漏洞',
                 'body': '仅列 CRITICAL/HIGH 漏洞及修复优先级，供应急响应使用。'}]
    return [{'heading': '概述',
             'body': f"目标 {scan_data.get('target', '')} 的扫描结果与风险分析。"}]


def render_report(scan_data: Dict, template: str = 'standard') -> Dict:
    """按模板渲染报告数据，返回 {title, template, vulns, sections}"""
    if template not in TEMPLATE_DEFS:
        template = 'standard'
    meta = TEMPLATE_DEFS[template]
    vulns = _filter_vulns(scan_data.get('vulnerabilities', []), template)
    vulns = sorted(vulns, key=lambda v: _SEV_RANK.get(str(v.get('severity', 'INFO')).upper(), 4))
    sections = _build_sections(scan_data, template)
    return {'title': meta['title'], 'template': template, 'vulns': vulns, 'sections': sections}
