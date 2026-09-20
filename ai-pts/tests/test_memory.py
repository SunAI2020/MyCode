"""
core.memory 单元测试：SessionMemory 与 Summarizer。

仅依赖 core.memory，不涉及 LLM / 执行器 / 网络。
"""
import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import SessionMemory, Summarizer


def _step_result(status="success", stdout="ok", error=""):
    """构造一个最小 StepResult 兼容对象（SimpleNamespace）。"""
    return SimpleNamespace(
        output=SimpleNamespace(
            status=SimpleNamespace(value=status),
            result={"returncode": 0, "stdout": stdout, "stderr": ""},
            evidence=["$ fake", stdout, ""],
            error=error,
            execution_time=0.1,
        )
    )


def test_add_step_records_fields():
    mem = SessionMemory(target_goal="get_shell")
    rec = mem.add_step(
        {"exploit_type": "rce", "tool": "wmiexec.py", "target": "10.0.0.1", "reason": "test"},
        _step_result(status="success", stdout="uid=0"),
    )
    assert len(mem.steps) == 1
    assert rec.index == 1
    assert rec.status == "success"
    assert rec.action["exploit_type"] == "rce"
    assert rec.result["stdout"] == "uid=0"


def test_to_context_includes_goal_services_vulns_steps():
    mem = SessionMemory(
        target_goal="get_shell",
        hosts=["10.0.0.1"],
        services=[{"host_ip": "10.0.0.1", "port": 445, "service_name": "microsoft-ds"}],
        vulns=[{"cve_id": "CVE-2020-1472", "severity": "critical", "description": "ZeroLogon"}],
    )
    mem.add_step(
        {"exploit_type": "rce", "tool": "wmiexec.py", "target": "10.0.0.1", "reason": "try"},
        _step_result(status="failed", error="exit 255"),
    )
    ctx = mem.to_context()
    assert "get_shell" in ctx
    assert "10.0.0.1" in ctx
    assert "CVE-2020-1472" in ctx
    assert "[1] [FAILED]" in ctx


def test_credential_redacted_in_context():
    mem = SessionMemory()
    mem.record_credential("10.0.0.1", "admin", password="secret")
    mem.set_privilege("10.0.0.1", "admin")
    ctx = mem.to_context()
    assert "pwd:***" in ctx
    assert "secret" not in ctx
    assert "10.0.0.1: admin" in ctx


def test_snapshot_is_json_serializable():
    mem = SessionMemory(target_goal="get_root")
    mem.add_step({"exploit_type": "privesc"}, _step_result())
    snap = mem.snapshot()
    assert snap["target_goal"] == "get_root"
    assert snap["steps"][0]["status"] == "success"
    json.dumps(snap)  # 不应抛异常


def test_summarizer_deterministic_fallback_without_fn():
    mem = SessionMemory()
    for i in range(10):
        mem.add_step({"exploit_type": "rce", "reason": f"step {i}"}, _step_result(stdout="x" * 100))
    summ = Summarizer(summarize_fn=None, max_steps=5, max_chars=999999, keep_recent=3)
    summ.maybe_summarize(mem)
    assert summ.summary  # 确定性退化仍有摘要
    assert len(mem.steps) == 3  # 只保留最近 3 步


def test_summarizer_uses_fn_and_accumulates():
    mem = SessionMemory()
    for i in range(10):
        mem.add_step({"exploit_type": "rce"}, _step_result(stdout="y" * 50))
    summ = Summarizer(summarize_fn=lambda text: "COMPRESSED", max_steps=5, keep_recent=3)
    summ.maybe_summarize(mem)
    assert summ.summary == "COMPRESSED"
    assert len(mem.steps) == 3


def test_summarizer_no_op_when_under_threshold():
    mem = SessionMemory()
    for i in range(3):
        mem.add_step({"exploit_type": "rce"}, _step_result())
    summ = Summarizer(summarize_fn=lambda text: "SHOULD_NOT_CALL", max_steps=5, keep_recent=2)
    summ.maybe_summarize(mem)
    assert summ.summary == ""
    assert len(mem.steps) == 3  # 未触发压缩，步骤保留
