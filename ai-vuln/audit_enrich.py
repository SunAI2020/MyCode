# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 代码审计发现 evidence/remediation 结构化富化模块

为每条代码审计发现生成结构化 evidence（证据）与 remediation（修复方案），
供报告、GUI、数据库持久化统一消费，避免各层重复实现。
"""
import re
import json
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 维度 key → 中文名（与 ai_code_reviewer.QUALITY_DIMENSIONS 保持一致）
DIMENSION_NAMES = {
    'security': '安全', 'architecture': '架构设计', 'logic': '逻辑问题',
    'function': '函数规范', 'completeness': '功能完整性', 'loop': '循环与复杂度',
    'invocation': '调用关系', 'interface': '接口规范', 'parameter': '参数传递',
    'naming': '命名标识', 'io': '输入输出', 'ui': '交互界面',
    'api': 'API设计', 'database': '数据库', 'supply_chain': '供应链',
}


def _dimension_name(finding: Dict) -> str:
    return DIMENSION_NAMES.get(str(finding.get('dimension') or '').lower(), '安全')


def build_evidence(finding: Dict) -> Dict:
    """生成结构化证据。summary 为一句话人读证据。"""
    file = finding.get('file') or ''
    line = finding.get('line') or ''
    category = finding.get('category') or ''
    dim = _dimension_name(finding)
    code = finding.get('code') or ''
    problem = finding.get('problem') or ''

    loc = f'{file}:{line}' if line else file
    summary = f'{loc} 处发现【{dim}·{category}】问题'

    return {
        'file': file,
        'line': line,
        'dimension': dim,
        'category': category,
        'severity': finding.get('severity') or 'INFO',
        'code': code,
        'problem': problem,
        'summary': summary,
    }


def _urgency(finding: Dict) -> str:
    sev = str(finding.get('severity') or '').upper()
    return {
        'CRITICAL': '立即修复',
        'HIGH': '紧急修复',
        'MEDIUM': '计划修复',
        'LOW': '排期修复',
        'INFO': '建议优化',
    }.get(sev, '视情况处理')


def _source(finding: Dict) -> str:
    if finding.get('source'):
        return str(finding['source']).strip().lower()
    if finding.get('ai_fix_suggestion'):
        return 'ai'
    return 'rule'


def _to_steps(text: str) -> List[str]:
    """把修复建议拆分为步骤列表（按中文分号/句号/换行）"""
    text = (text or '').strip()
    if not text:
        return []
    parts = re.split(r'[；;。]\s*|\n+', text)
    parts = [p.strip() for p in parts if p.strip()]
    return parts or [text]


def build_remediation(finding: Dict) -> Dict:
    """生成结构化修复方案。优先级：AI 建议 > 规则库 > 通用回退。"""
    ai = (finding.get('ai_fix_suggestion') or '').strip()
    rec = ai or (finding.get('recommendation') or '').strip()
    source = 'ai' if ai else _source(finding)

    if not rec:
        rec = '根据问题类型进行针对性修复，详见代码上下文与最佳实践。'
        source = 'generic'

    return {
        'summary': rec[:200],
        'steps': _to_steps(rec),
        'source': source,
        'urgency': _urgency(finding),
    }


def enrich_audit_findings(findings: List[Dict]) -> List[Dict]:
    """批量富化：evidence 缺失时填充；remediation 每次重算。"""
    for f in findings:
        if not isinstance(f, dict):
            continue
        if not isinstance(f.get('evidence'), dict):
            f['evidence'] = build_evidence(f)
        f['remediation'] = build_remediation(f)
    return findings


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


def evidence_dict(finding: Dict) -> Dict:
    """安全获取结构化 evidence（兼容 DB 反序列化）。"""
    return _as_dict(finding.get('evidence')) or build_evidence(finding)


def remediation_dict(finding: Dict) -> Dict:
    """安全获取结构化 remediation（兼容 DB 反序列化）。"""
    if (finding.get('ai_fix_suggestion') or '').strip():
        return build_remediation(finding)
    return _as_dict(finding.get('remediation')) or build_remediation(finding)
