# -*- coding: utf-8 -*-
"""workflow 状态机单元测试"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflow import VulnWorkflow


class TestStateMachine:
    def test_valid_transitions(self):
        assert VulnWorkflow.can_transition('OPEN', 'CONFIRMED')
        assert VulnWorkflow.can_transition('CONFIRMED', 'IN_PROGRESS')
        assert VulnWorkflow.can_transition('IN_PROGRESS', 'FIXED')
        assert VulnWorkflow.can_transition('FIXED', 'VERIFIED')
        assert VulnWorkflow.can_transition('VERIFIED', 'CLOSED')

    def test_invalid_transitions(self):
        assert not VulnWorkflow.can_transition('OPEN', 'FIXED')
        assert not VulnWorkflow.can_transition('OPEN', 'CLOSED')
        assert not VulnWorkflow.can_transition('CONFIRMED', 'OPEN')

    def test_terminal_no_transition(self):
        assert not VulnWorkflow.can_transition('FALSE_POSITIVE', 'CONFIRMED')
        assert not VulnWorkflow.can_transition('DUPLICATE', 'OPEN')

    def test_reopen_from_closed(self):
        assert VulnWorkflow.can_transition('CLOSED', 'REOPENED')
        assert VulnWorkflow.can_transition('REOPENED', 'CONFIRMED')

    def test_unknown_state_rejected(self):
        assert not VulnWorkflow.can_transition('OPEN', 'NOT_A_STATE')

    def test_is_terminal(self):
        assert VulnWorkflow.is_terminal('FALSE_POSITIVE')
        assert VulnWorkflow.is_terminal('DUPLICATE')
        assert not VulnWorkflow.is_terminal('OPEN')


class TestTransitionWithDB:
    def test_transition_happy_path(self, db):
        wid = db.create_disposition('CVE-2021-44228', vuln_title='Log4Shell', severity='CRITICAL')
        wf = VulnWorkflow(db=db)
        r = wf.transition(wid, 'CONFIRMED', assignee='analyst1')
        assert r['success'] is True
        assert r['from_status'] == 'OPEN'
        assert r['to_status'] == 'CONFIRMED'
        assert db.get_disposition(wid)['status'] == 'CONFIRMED'
        assert db.get_disposition(wid)['assignee'] == 'analyst1'

    def test_transition_invalid_rejected(self, db):
        wid = db.create_disposition('CVE-2020-1234', vuln_title='X')
        wf = VulnWorkflow(db=db)
        r = wf.transition(wid, 'CLOSED')  # OPEN → CLOSED 非法
        assert r['success'] is False
        assert '非法流转' in r['reason']
        assert db.get_disposition(wid)['status'] == 'OPEN'

    def test_transition_nonexistent(self, db):
        wf = VulnWorkflow(db=db)
        r = wf.transition(999999, 'CONFIRMED')
        assert r['success'] is False

    def test_full_closure_cycle(self, db):
        wid = db.create_disposition('CVE-2021-41733', vuln_title='Path Traversal')
        wf = VulnWorkflow(db=db)
        for state in ['CONFIRMED', 'IN_PROGRESS', 'FIXED', 'VERIFIED', 'CLOSED']:
            r = wf.transition(wid, state)
            assert r['success'] is True, f'{state}: {r}'
        assert db.get_disposition(wid)['status'] == 'CLOSED'
        assert db.get_disposition(wid)['closed_at'] is not None

    def test_reopen_clears_closed_at(self, db):
        wid = db.create_disposition('CVE-2021-44228', vuln_title='Log4Shell')
        wf = VulnWorkflow(db=db)
        for state in ['CONFIRMED', 'IN_PROGRESS', 'FIXED', 'VERIFIED', 'CLOSED']:
            assert wf.transition(wid, state)['success']
        assert db.get_disposition(wid)['closed_at'] is not None
        assert wf.transition(wid, 'REOPENED')['success']
        assert db.get_disposition(wid)['status'] == 'REOPENED'
        assert db.get_disposition(wid)['closed_at'] is None
