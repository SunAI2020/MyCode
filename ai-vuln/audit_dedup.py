# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 代码审计发现相似度去重模块

基于 (file, dimension, category, code) 的相似度去重：
同一文件同一维度同一类别下，行号相同或代码高度相似的多条发现视为重复，
保留严重度最高（信息最全）的一条。
"""
import logging
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 判定重复的相似度阈值（保守：仅高相似度判重，避免误删真实独立问题）
SIMILARITY_THRESHOLD = 0.85

SEVERITY_ORDER = {'CRITICAL': 5, 'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'INFO': 1}


def fingerprint(finding: Dict) -> Tuple[str, str, str]:
    """代码审计发现去重指纹：(file, dimension, category)"""
    return (
        str(finding.get('file') or '').strip(),
        str(finding.get('dimension') or '').strip().lower(),
        str(finding.get('category') or '').strip().lower(),
    )


def _valid_line(value) -> bool:
    """行号是否为有效的正整数（0/None/空串表示行号缺失，不用于判重）"""
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def _code_similarity(a: Dict, b: Dict) -> float:
    """代码片段相似度（difflib）"""
    ca = (a.get('code') or '').strip()
    cb = (b.get('code') or '').strip()
    if not ca or not cb:
        return 0.0
    return SequenceMatcher(None, ca, cb).ratio()


def similarity(a: Dict, b: Dict) -> float:
    """两条代码审计发现的相似度 0-1"""
    if fingerprint(a) != fingerprint(b):
        return 0.0
    la, lb = a.get('line'), b.get('line')
    # 同文件+维度+类别+行号 → 确定重复（行号缺失 0/None 不参与此规则，避免误判重复）
    if _valid_line(la) and _valid_line(lb) and int(la) == int(lb):
        return 1.0
    s = _code_similarity(a, b)
    if s >= 0.6:
        return s
    # 行号相邻且同类别，兜底判重
    try:
        if la and lb and abs(int(la) - int(lb)) <= 1:
            return 0.7
    except (TypeError, ValueError):
        pass
    return s


def _priority(finding: Dict) -> Tuple:
    """保留优先级：严重度 > 信息完整度（问题描述 + 方案长度）"""
    return (
        SEVERITY_ORDER.get(str(finding.get('severity', '')).upper(), 0),
        len(str(finding.get('problem') or '')) + len(str(finding.get('recommendation') or '')),
    )


class AuditDeduplicator:
    """代码审计发现相似度去重器"""

    def __init__(self, threshold: float = SIMILARITY_THRESHOLD):
        self.threshold = threshold

    def deduplicate(self, findings: List[Dict]) -> Dict[str, List[Dict]]:
        """去重，返回 {'unique': [...], 'duplicates': [...]}

        先按优先级降序排序，保证每组第一条即最优保留项；后续相似项标记为重复。
        """
        ordered = sorted(findings, key=_priority, reverse=True)
        unique: List[Dict] = []
        duplicates: List[Dict] = []
        for f in ordered:
            dup_of = next((k for k in unique if similarity(f, k) >= self.threshold), None)
            if dup_of is None:
                unique.append(dict(f))
            else:
                tagged = dict(f)
                tagged['duplicate'] = True
                tagged['duplicate_of'] = dup_of.get('category') or dup_of.get('file')
                duplicates.append(tagged)
        return {'unique': unique, 'duplicates': duplicates}
