"""
core.report_builder 测试：loop_steps_to_attack_steps 映射。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.report_builder import loop_steps_to_attack_steps


def test_loop_steps_to_attack_steps():
    steps = [{
        "action": {"exploit_type": "rce", "tool": "wmiexec.py", "target": "10.0.0.1", "description": "d"},
        "status": "success", "error": "", "evidence": ["$ cmd", "out", ""],
    }]
    out = loop_steps_to_attack_steps(steps)
    assert len(out) == 1
    assert out[0]["exploit_type"] == "rce"
    assert out[0]["tool"] == "wmiexec.py"
    assert out[0]["target"] == "10.0.0.1"
    assert out[0]["status"] == "success"
    assert out[0]["evidence"] == ["$ cmd", "out", ""]


def test_loop_steps_to_attack_steps_skips_non_dict():
    out = loop_steps_to_attack_steps([None, "x"])
    assert out == []
