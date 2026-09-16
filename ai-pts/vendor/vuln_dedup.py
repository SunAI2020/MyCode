# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 漏洞相似度去重模块

基于 (cve_id, host, service, 版本前缀) 指纹的相似度去重：
同一主机同一服务上匹配到同一 CVE 的多条记录视为重复，保留优先级最高的一条。
"""
import re
import logging
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 判定重复的相似度阈值（保守：仅高相似度判重，避免误删真实独立漏洞）
SIMILARITY_THRESHOLD = 0.9


def _norm_version(version) -> Tuple[int, int]:
    """提取 major.minor 版本号元组（缺失返回空元组）"""
    m = re.search(r'(\d+)\.(\d+)', str(version or ''))
    if not m:
        return ()
    return (int(m.group(1)), int(m.group(2)))


def fingerprint(vuln: Dict) -> Tuple[str, str, str, str]:
    """漏洞去重指纹：(cve_id, host, service, port)——不同端口是不同监听实例"""
    return (
        str(vuln.get('cve_id') or '').strip().upper(),
        str(vuln.get('host') or '').strip(),
        str(vuln.get('service') or '').strip().lower(),
        str(vuln.get('port') or '').strip(),
    )


def similarity(a: Dict, b: Dict) -> float:
    """两条漏洞的相似度 0-1"""
    if fingerprint(a) != fingerprint(b):
        return 0.0
    va, vb = _norm_version(a.get('version')), _norm_version(b.get('version'))
    if not va or not vb:
        # 版本缺失，仅 CVE+host+service 一致，给阈值线上相似度
        return 0.9
    if va == vb:
        return 1.0
    return 0.0


def _confidence_score(vuln: Dict) -> float:
    c = vuln.get('ai_confidence')
    if isinstance(c, (int, float)):
        return float(c)
    return {'high': 0.9, 'medium': 0.6, 'low': 0.3}.get(str(c).lower(), 0.0)


def _num(v):
    """把数值字段统一为 float，避免 int/str 混用导致 sorted 抛 TypeError。"""
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _priority(vuln: Dict) -> Tuple:
    """保留优先级：风险评分 > AI 置信度 > CVSS"""
    return (
        _num(vuln.get('risk_score')),
        _confidence_score(vuln),
        _num(vuln.get('cvss_score')),
    )


class VulnDeduplicator:
    """漏洞相似度去重器"""

    def __init__(self, threshold: float = SIMILARITY_THRESHOLD):
        self.threshold = threshold

    def deduplicate(self, vulns: List[Dict]) -> Dict[str, List[Dict]]:
        """去重，返回 {'unique': [...], 'duplicates': [...]}

        先按优先级降序排序，保证每组第一条即最优保留项；后续相似项标记为重复。
        """
        ordered = sorted(vulns, key=_priority, reverse=True)
        unique: List[Dict] = []
        duplicates: List[Dict] = []
        for v in ordered:
            dup_of = next((k for k in unique if similarity(v, k) >= self.threshold), None)
            if dup_of is None:
                unique.append(dict(v))
            else:
                tagged = dict(v)
                tagged['duplicate'] = True
                tagged['duplicate_of'] = dup_of.get('cve_id')
                duplicates.append(tagged)
        return {'unique': unique, 'duplicates': duplicates}
