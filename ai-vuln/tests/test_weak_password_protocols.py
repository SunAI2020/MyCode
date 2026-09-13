# -*- coding: utf-8 -*-
"""弱口令协议扩充测试"""
from weak_password_scanner import (
    SUPPORTED_PROTOCOLS, SERVICE_PROTOCOL_MAP, HANDLER_REGISTRY, WeakPasswordScanner,
)


def test_new_protocols_supported():
    for p in ('mysql', 'postgresql', 'redis', 'mongodb', 'rdp', 'telnet'):
        assert p in SUPPORTED_PROTOCOLS


def test_service_protocol_mapping():
    assert SERVICE_PROTOCOL_MAP['mysql'] == 'mysql'
    assert SERVICE_PROTOCOL_MAP['postgres'] == 'postgresql'
    assert SERVICE_PROTOCOL_MAP['mongod'] == 'mongodb'
    assert SERVICE_PROTOCOL_MAP['ms-wbt-server'] == 'rdp'
    assert SERVICE_PROTOCOL_MAP['telnet'] == 'telnet'


def test_handlers_registered():
    for p in ('mysql', 'postgresql', 'redis', 'mongodb', 'rdp', 'telnet'):
        assert p in HANDLER_REGISTRY


def test_handlers_have_availability_flag():
    for p in ('mysql', 'postgresql', 'redis', 'mongodb', 'rdp', 'telnet'):
        assert hasattr(HANDLER_REGISTRY[p], 'available')


def test_map_protocol_via_scanner():
    s = WeakPasswordScanner(db=None)
    assert s.map_protocol('mysql') == 'mysql'
    assert s.map_protocol('postgresql') == 'postgresql'


def test_unsupported_protocol_returns_reason():
    s = WeakPasswordScanner(db=None)
    r = s.scan('10.0.0.1', 3306, 'mssql')
    assert r['service_supported'] is False
    assert r['reason']


def test_lockout_avoidance_breaks_on_consecutive_failures(monkeypatch):
    from weak_password_scanner import HANDLER_REGISTRY, WeakPasswordScanner

    class AlwaysFailHandler:
        protocol = 'http'
        available = True

        def __init__(self):
            self.calls = 0

        def check(self, *a, **kw):
            self.calls += 1
            return False

    h = AlwaysFailHandler()
    monkeypatch.setitem(HANDLER_REGISTRY, 'http', h)
    creds = [{'username': 'u1', 'password': 'p1'},
             {'username': 'u2', 'password': 'p2'},
             {'username': 'u3', 'password': 'p3'}]
    s = WeakPasswordScanner(db=None, delay_between_attempts=0, max_failures_before_break=2)
    r = s.scan('10.0.0.1', 80, 'http', credentials=creds)
    assert r['attempts'] == 2
    assert '锁定' in r['reason']
    assert h.calls == 2
