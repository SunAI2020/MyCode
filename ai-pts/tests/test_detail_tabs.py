"""
gui.detail_tabs 测试：derive_verify_action 动作推导。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.detail_tabs import derive_verify_action


def test_derive_url_from_http_target():
    assert derive_verify_action({"target": "http://x.com/orders/1"}, {}) == \
        ("url", "http://x.com/orders/1")


def test_derive_url_from_parsed_matched_at():
    step_result = {"result": {"parsed": {"matches": [{"matched_at": "http://x.com/api"}]}}}
    assert derive_verify_action({"target": "10.0.0.1"}, step_result) == \
        ("url", "http://x.com/api")


def test_derive_command_from_validation_cmd():
    assert derive_verify_action({"target": "10.0.0.1", "validation_cmd": "whoami"}, {}) == \
        ("command", "whoami")


def test_derive_command_from_evidence():
    step_result = {"evidence": ["$ sqlmap -u http://x.com --batch", "out", ""]}
    assert derive_verify_action({"target": "10.0.0.1"}, step_result) == \
        ("command", "sqlmap -u http://x.com --batch")


def test_derive_none():
    assert derive_verify_action({"target": "10.0.0.1"}, {}) is None
