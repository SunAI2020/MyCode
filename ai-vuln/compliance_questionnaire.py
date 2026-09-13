# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 合规问卷引擎

负责『哪些条款要人填、填了什么、填到什么程度』：
从条款目录抽取待填条款、读写答案、统计完成度，并统一 scope_key 解析规则。

scope_key 规则（组织级答案跨业务系统复用，避免逐系统重复填报）：
  条款 scope='org'    → 'ORG'
  条款 scope='system' → 资产的 business_system，为空时回退 'DEFAULT'
"""
import logging
from typing import List, Dict, Optional, Any

from compliance_engine import (
    ComplianceEngine, ComplianceControl,
    STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_NA, STATUS_UNFILLED,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ORG_SCOPE = 'ORG'
DEFAULT_SYSTEM_SCOPE = 'DEFAULT'

# 问卷可选状态（不含『证据不足』——那是技术侧判定，人工不填）
ANSWERABLE_STATUSES = (STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_NA)


def resolve_scope_key(control: ComplianceControl, business_system: str = '') -> str:
    """条款作用域 → 存储键。组织级条款一律落在 ORG。"""
    if control.scope == 'org':
        return ORG_SCOPE
    return (business_system or '').strip() or DEFAULT_SYSTEM_SCOPE


def system_scope_key(business_system: str = '') -> str:
    """业务系统维度的 scope_key（用于批量读取答案）"""
    return (business_system or '').strip() or DEFAULT_SYSTEM_SCOPE


def normalize_status(status: Any) -> Optional[str]:
    """把界面/AI 传来的状态归一化。无法识别时返回 None，绝不猜成『符合』。"""
    if not status:
        return None
    s = str(status).strip()
    if s in ANSWERABLE_STATUSES:
        return s
    alias = {
        '合规': STATUS_PASS, '通过': STATUS_PASS, 'pass': STATUS_PASS, 'yes': STATUS_PASS,
        '部分': STATUS_PARTIAL, 'partial': STATUS_PARTIAL,
        '不合规': STATUS_FAIL, '未通过': STATUS_FAIL, 'fail': STATUS_FAIL, 'no': STATUS_FAIL,
        'na': STATUS_NA, 'n/a': STATUS_NA, '不涉及': STATUS_NA,
    }
    return alias.get(s.lower())


class QuestionnaireEngine:
    """合规问卷引擎：条款目录 ↔ 数据库答案 之间的适配层"""

    def __init__(self, standard: str, db=None, level: str = 'ALL'):
        """
        Args:
            standard: 标准标识（dengbao / cii / data_security）
            db: Database 门面或 ComplianceResultsDB；None 时为只读模式（仅列条款）
            level: 等级过滤（等保 L2/L3；其它标准用 ALL）
        """
        self.standard = standard
        self.level = level or 'ALL'
        self.engine = ComplianceEngine(standard)
        self._db = db

    # ---- 数据库适配：门面与子库都能用 ----
    @property
    def store(self):
        if self._db is None:
            return None
        return getattr(self._db, 'compliance', self._db)

    # ---- 条款 ----
    def controls(self) -> List[ComplianceControl]:
        """本标准本等级下需要人工填报的条款（questionnaire + hybrid）"""
        return self.engine.questionnaire_controls(self.level)

    def controls_by_domain(self) -> Dict[str, List[ComplianceControl]]:
        """按安全域分组，供问卷界面分页/分组展示"""
        grouped: Dict[str, List[ComplianceControl]] = {}
        for c in self.controls():
            grouped.setdefault(c.domain or '未分类', []).append(c)
        return grouped

    def get_control(self, control_id: str) -> Optional[ComplianceControl]:
        for c in self.engine.controls:
            if c.id == control_id:
                return c
        return None

    # ---- 答案读写 ----
    def load_answers(self, business_system: str = '') -> Dict[str, Dict]:
        """读取答案：ORG 全局答案 + 该业务系统答案（后者覆盖前者）"""
        if self.store is None:
            return {}
        return self.store.get_answers(self.standard,
                                      system_scope_key(business_system),
                                      include_org=True)

    def save_answer(self, control_id: str, status: str, note: str = '',
                    business_system: str = '', evidence_ref: str = '',
                    answered_by: str = '') -> bool:
        """保存一条答案。状态非法时拒绝写入并返回 False，不静默落一个坏值。"""
        if self.store is None:
            logger.warning('问卷引擎处于只读模式，忽略保存请求')
            return False
        control = self.get_control(control_id)
        if control is None:
            logger.warning(f'条款不存在，拒绝保存答案: {control_id}')
            return False
        norm = normalize_status(status)
        if norm is None:
            logger.warning(f'非法的填报状态，拒绝保存: {control_id} -> {status!r}')
            return False
        self.store.upsert_answer(self.standard, control_id, norm, note or '',
                                 resolve_scope_key(control, business_system),
                                 evidence_ref or '', answered_by or '')
        return True

    def save_answers(self, answers: Dict[str, Dict], business_system: str = '',
                     answered_by: str = '') -> Dict[str, int]:
        """批量保存。返回 {'saved': n, 'rejected': m}，被拒条目会记日志。"""
        saved = rejected = 0
        for cid, ans in (answers or {}).items():
            ans = ans or {}
            ok = self.save_answer(cid, ans.get('status'), ans.get('note', ''),
                                  business_system, ans.get('evidence_ref', ''),
                                  ans.get('answered_by') or answered_by)
            saved += 1 if ok else 0
            rejected += 0 if ok else 1
        return {'saved': saved, 'rejected': rejected}

    def clear_answer(self, control_id: str, business_system: str = '') -> bool:
        if self.store is None:
            return False
        control = self.get_control(control_id)
        if control is None:
            return False
        self.store.delete_answer(self.standard, control_id,
                                 resolve_scope_key(control, business_system))
        return True

    # ---- 完成度 ----
    def pending_controls(self, business_system: str = '') -> List[ComplianceControl]:
        """尚未填报的条款"""
        answers = self.load_answers(business_system)
        return [c for c in self.controls()
                if normalize_status((answers.get(c.id) or {}).get('status')) is None]

    def progress(self, business_system: str = '') -> Dict:
        """填报进度。无待填条款时 rate 为 None，不伪装成 100%。"""
        controls = self.controls()
        answers = self.load_answers(business_system)
        total = len(controls)
        filled = 0
        by_domain: Dict[str, Dict] = {}
        for c in controls:
            answered = normalize_status((answers.get(c.id) or {}).get('status')) is not None
            filled += 1 if answered else 0
            d = by_domain.setdefault(c.domain or '未分类', {'total': 0, 'filled': 0})
            d['total'] += 1
            d['filled'] += 1 if answered else 0
        for d in by_domain.values():
            d['rate'] = round(d['filled'] / d['total'], 4) if d['total'] else None
        return {
            'standard': self.standard,
            'level': self.level,
            'scope_key': system_scope_key(business_system),
            'total': total,
            'filled': filled,
            'pending': total - filled,
            'rate': round(filled / total, 4) if total else None,
            'by_domain': by_domain,
        }

    # ---- 表格视图 ----
    def to_rows(self, business_system: str = '') -> List[Dict]:
        """问卷表格行，供 GUI / API 直接渲染"""
        answers = self.load_answers(business_system)
        rows = []
        for c in self.controls():
            ans = answers.get(c.id) or {}
            status = normalize_status(ans.get('status'))
            rows.append({
                'control_id': c.id,
                'domain': c.domain,
                'category': c.category,
                'title': c.title,
                'requirement': c.requirement,
                'question': c.question,
                'options': list(c.options),
                'evidence_hint': c.evidence_hint,
                'scope': c.scope,
                'scope_key': resolve_scope_key(c, business_system),
                'mode': c.mode,
                'weight': c.weight,
                'status': status or STATUS_UNFILLED,
                'note': ans.get('note', '') or '',
                'evidence_ref': ans.get('evidence_ref', '') or '',
                'answered_by': ans.get('answered_by', '') or '',
                'updated_at': ans.get('updated_at', '') or '',
                'answered': status is not None,
            })
        return rows
