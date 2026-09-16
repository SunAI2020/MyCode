# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 漏洞 evidence/remediation 结构化富化模块

为每条漏洞生成结构化 evidence（证据）与 remediation（修复方案），
供报告、GUI、数据库持久化统一消费，避免各层重复实现。
"""
import json
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 服务 → 修复步骤（集中管理，自 report_generator._generate_risk_analysis 迁移而来）
SERVICE_REMEDIATION: Dict[str, List[str]] = {
    'smb': ['升级Samba到最新稳定版本', '禁用SMBv1协议', '启用SMB签名和加密', '限制445端口访问来源IP'],
    'msrpc': ['安装最新Windows安全更新', '配置Windows防火墙限制RPC访问', '禁用不必要的RPC服务'],
    'microsoft-ds': ['安装最新Windows安全更新', '配置防火墙限制445端口', '启用SMB签名'],
    'ssh': ['升级OpenSSH到最新版本', '禁用弱加密算法和过时协议', '使用密钥认证替代密码', '配置fail2ban防暴力破解'],
    'http': ['升级Web服务器到最新版本', '配置WAF防护', '实施安全头(HSTS, CSP等)', '定期安全扫描'],
    'rdp': ['启用网络级别身份验证(NLA)', '限制RDP访问来源IP', '启用账号锁定策略'],
    'mysql': ['升级到最新MySQL版本', '限制远程访问', '启用SSL连接', '最小权限原则'],
    'redis': ['设置requirepass强密码', '禁用危险命令(FLUSHALL等)', '绑定localhost', '启用protected-mode'],
}


def _generic_remediation_steps(vuln: Dict) -> List[str]:
    """通用 CVE 回退修复步骤"""
    cve_id = vuln.get('cve_id') or ''
    ref = f'参考{cve_id}官方公告获取补丁' if cve_id else '参考官方公告获取补丁'
    return [ref, '升级受影响的软件到安全版本', '实施最小权限原则', '配置防火墙限制暴露面']


def _references(vuln: Dict) -> List[str]:
    """收集参考链接：NVD 详情页 + references_url（保序去重）"""
    refs: List[str] = []
    seen = set()

    def _add(r):
        r = (r or '').strip()
        if r and r not in seen:
            seen.add(r)
            refs.append(r)

    cve_id = (vuln.get('cve_id') or '').strip()
    if cve_id and cve_id.upper() != 'N/A':
        _add(f'https://nvd.nist.gov/vuln/detail/{cve_id}')
    _add(vuln.get('references_url') or '')
    return refs


def _urgency(vuln: Dict) -> str:
    """基于 KEV / 严重程度 / CVSS 的修复紧急度"""
    if vuln.get('kev'):
        return '立即修复! (CISA KEV 在野利用)'
    sev = (vuln.get('severity') or '').upper()
    cvss = vuln.get('cvss_score')
    try:
        s = float(cvss) if cvss is not None else 0.0
    except (TypeError, ValueError):
        s = 0.0
    if sev == 'CRITICAL' or s >= 9.0:
        return '立即修复 (0-4小时)'
    if sev == 'HIGH' or s >= 7.0:
        return '紧急修复 (24小时内)'
    if sev == 'MEDIUM' or s >= 4.0:
        return '计划修复 (72小时内)'
    if sev == 'LOW' or s >= 0.1:
        return '排期修复 (30天内)'
    return '视情况处理'


def _matched_by(vuln: Dict) -> str:
    """推断匹配维度（用于证据展示）"""
    if not vuln.get('cve_id'):
        return 'open_service'
    parts = []
    for key in ('version', 'product', 'service', 'port'):
        if vuln.get(key):
            parts.append(key)
    return '+'.join(parts) if parts else 'service'


def build_evidence(vuln: Dict) -> Dict:
    """生成结构化证据。summary 为一句话人读证据。"""
    service = vuln.get('service') or '未知服务'
    version = vuln.get('version') or vuln.get('product') or ''
    port = vuln.get('port') or ''
    host = vuln.get('host') or ''
    cve_id = vuln.get('cve_id') or ''

    ver_text = f' {version}' if version else ''
    port_text = f' 开放于端口 {port}' if port else ''
    if cve_id:
        summary = f'{host} 的 {service}{ver_text} 服务{port_text}，命中 {cve_id}'
    else:
        summary = f'{host} 检测到开放服务: {service}{ver_text}{port_text}'

    return {
        'host': host,
        'port': port,
        'protocol': vuln.get('protocol') or 'tcp',
        'service': service,
        'version': version,
        'product': vuln.get('product') or '',
        'cve_id': cve_id,
        'cvss_score': vuln.get('cvss_score'),
        'severity': vuln.get('severity') or 'INFO',
        'kev': bool(vuln.get('kev', False)),
        'references': _references(vuln),
        'matched_by': _matched_by(vuln),
        'summary': summary,
    }


def build_remediation(vuln: Dict) -> Dict:
    """生成结构化修复方案。优先级：AI 建议 > 规则库 > 通用回退。"""
    ai = (vuln.get('ai_remediation') or '').strip()
    if ai:
        steps = [ai]
        source = 'ai'
        summary = ai
    else:
        service = (vuln.get('service') or '').strip().lower()
        if service in SERVICE_REMEDIATION:
            steps = SERVICE_REMEDIATION[service]
            source = 'rule'
        else:
            steps = _generic_remediation_steps(vuln)
            source = 'generic'
        summary = steps[0] if steps else ''

    return {
        'summary': summary,
        'steps': steps,
        'source': source,
        'urgency': _urgency(vuln),
        'references': _references(vuln),
    }


def enrich_vulnerabilities(vulns: List[Dict]) -> List[Dict]:
    """批量富化：evidence 仅在缺失时填充；remediation 每次重算。

    重算 remediation 的目的：AI 核验追加 ai_remediation 后重跑本函数，
    即可把修复来源从 rule/generic 刷新为 ai。
    """
    for v in vulns:
        if not isinstance(v, dict):
            continue
        if not isinstance(v.get('evidence'), dict):
            v['evidence'] = build_evidence(v)
        v['remediation'] = build_remediation(v)
    return vulns


def _as_dict(value) -> Optional[Dict]:
    """把 dict 或 JSON 字符串归一化为 dict（DB 持久化后为字符串）。"""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            obj = json.loads(value)
            if isinstance(obj, dict):
                return obj
        except (ValueError, TypeError):
            pass
    return None


def evidence_dict(vuln: Dict) -> Dict:
    """安全获取结构化 evidence（兼容 DB 反序列化）。"""
    return _as_dict(vuln.get('evidence')) or build_evidence(vuln)


def remediation_dict(vuln: Dict) -> Dict:
    """安全获取结构化 remediation（兼容 DB 反序列化）。

    若存在 ai_remediation（AI 核验后）则以最新为准重算，保证来源为 ai；
    否则（历史 DB 数据，无 ai_remediation）返回已持久化的结构。
    """
    if (vuln.get('ai_remediation') or '').strip():
        return build_remediation(vuln)
    return _as_dict(vuln.get('remediation')) or build_remediation(vuln)
