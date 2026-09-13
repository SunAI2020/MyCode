# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 漏洞处置工作流状态机

实现漏洞处置管理闭环：
OPEN → CONFIRMED → IN_PROGRESS → FIXED → VERIFIED → CLOSED
另含 FALSE_POSITIVE / DUPLICATE 终态，以及 REOPENED 回退。
非法流转被状态机拒绝，保证处置过程可审计、可追溯。
"""
import logging
from typing import Dict, List, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VulnWorkflow:
    """漏洞处置工作流状态机"""

    # 全部合法状态
    STATES = [
        'OPEN', 'CONFIRMED', 'IN_PROGRESS', 'FIXED',
        'VERIFIED', 'CLOSED', 'REOPENED', 'FALSE_POSITIVE', 'DUPLICATE',
    ]

    # 终态（不可再流转，但 CLOSED 允许重开）
    TERMINAL_STATES = {'FALSE_POSITIVE', 'DUPLICATE'}

    # 合法流转表：from → 允许的 to 集合
    VALID_TRANSITIONS: Dict[str, set] = {
        'OPEN': {'CONFIRMED', 'IN_PROGRESS', 'FALSE_POSITIVE', 'DUPLICATE'},
        'CONFIRMED': {'IN_PROGRESS', 'FALSE_POSITIVE', 'DUPLICATE'},
        'IN_PROGRESS': {'FIXED', 'REOPENED', 'FALSE_POSITIVE'},
        'FIXED': {'VERIFIED', 'REOPENED', 'FALSE_POSITIVE'},
        'VERIFIED': {'CLOSED', 'REOPENED'},
        'CLOSED': {'REOPENED'},
        'REOPENED': {'CONFIRMED', 'IN_PROGRESS', 'FIXED', 'FALSE_POSITIVE'},
        'FALSE_POSITIVE': set(),
        'DUPLICATE': set(),
    }

    def __init__(self, db=None):
        self.db = db

    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        """判断状态流转是否合法（纯函数，可单测）"""
        if to_status not in cls.STATES:
            return False
        if from_status in cls.TERMINAL_STATES:
            return False
        return to_status in cls.VALID_TRANSITIONS.get(from_status, set())

    @classmethod
    def is_terminal(cls, status: str) -> bool:
        return status in cls.TERMINAL_STATES

    def transition(self, disposition_id: int, to_status: str,
                   assignee: Optional[str] = None, note: Optional[str] = None,
                   reopen_reason: Optional[str] = None) -> Dict[str, Any]:
        """执行一次状态流转（校验 + 持久化）"""
        if self.db is None:
            return {'success': False, 'reason': '未提供数据库实例'}

        current = self.db.get_disposition(disposition_id)
        if current is None:
            return {'success': False, 'reason': f'处置记录 {disposition_id} 不存在'}

        from_status = current.get('status', 'OPEN')
        if not self.can_transition(from_status, to_status):
            return {
                'success': False,
                'reason': f'非法流转: {from_status} → {to_status}',
                'current_status': from_status,
            }

        self.db.update_disposition(disposition_id, status=to_status,
                                   assignee=assignee, note=note,
                                   reopen_reason=reopen_reason)
        logger.info(f'漏洞处置 {disposition_id}: {from_status} → {to_status}')
        return {
            'success': True,
            'from_status': from_status,
            'to_status': to_status,
            'disposition': self.db.get_disposition(disposition_id),
        }
