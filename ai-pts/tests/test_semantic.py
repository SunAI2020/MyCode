"""
core.semantic 测试：SemanticVerifier（mock llm + 回退）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.semantic import SemanticVerifier


def test_verify_confirmed_and_rejected():
    calls = {"n": 0}

    def llm(system, user):
        calls["n"] += 1
        return {"is_real": calls["n"] == 1, "confidence": "high", "reason": "r"}

    v = SemanticVerifier(llm)
    out = v.verify([{"id": 1, "name": "sqli"}, {"id": 2, "name": "xss"}])
    assert out[0]["verify_status"] == "confirmed"
    assert out[1]["verify_status"] == "rejected"


def test_verify_fallback_unverified_when_llm_raises():
    def llm(system, user):
        raise RuntimeError("boom")

    v = SemanticVerifier(llm)
    out = v.verify([{"id": 1}])
    assert out[0]["verify_status"] == "unverified"


def test_verify_no_llm_unverified():
    v = SemanticVerifier(None)
    out = v.verify([{"id": 1}])
    assert out[0]["verify_status"] == "unverified"
