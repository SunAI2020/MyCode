"""
Phase 4 新增执行器测试：Sqlmap / Nuclei / Semgrep 的 build_command 与校验。
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.workflow import StepInput
from core.executors.sqli import SqlmapExecutor
from core.executors.web_exploit import NucleiExecutor
from core.executors.code_audit import SemgrepExecutor


def _in(target):
    return StepInput(target=target)


def test_sqlmap_build_command():
    ex = SqlmapExecutor(require_confirmation=False)
    cmd = ex.build_command(_in("http://t.local/page?id=1"), {})
    assert cmd == ["sqlmap", "-u", "http://t.local/page?id=1", "--batch"]


def test_sqlmap_rejects_non_url():
    ex = SqlmapExecutor(require_confirmation=False)
    assert ex.build_command(_in("not-a-url"), {}) is None


def test_nuclei_build_command():
    ex = NucleiExecutor(require_confirmation=False)
    cmd = ex.build_command(_in("http://t.local"), {"severity": "high"})
    # B4：nuclei 加 -jsonl 以便结构化解析
    assert cmd == ["nuclei", "-u", "http://t.local", "-jsonl", "-silent", "-severity", "high"]


def test_nuclei_rejects_non_url():
    ex = NucleiExecutor(require_confirmation=False)
    assert ex.build_command(_in("192.168.1.1"), {}) is None


def test_semgrep_build_command():
    ex = SemgrepExecutor(require_confirmation=False)
    cmd = ex.build_command(_in("/src/repo"), {})
    # B4：semgrep 加 --json --no-error 以便结构化解析且不把「发现漏洞」误判为失败
    assert cmd == ["semgrep", "--json", "--no-error", "--config", "p/owasp-top-ten", "/src/repo"]


def test_semgrep_validate_local_path():
    ex = SemgrepExecutor(require_confirmation=False)
    ex._tool_available = lambda tool=None: True
    assert asyncio.run(ex.validate(_in("/src/repo"))) is True
    assert asyncio.run(ex.validate(_in(""))) is False
