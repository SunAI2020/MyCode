"""
core.business_logic 测试：差分验证 + 检测器编排（mock LLM + mock executor）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.business_logic import HttpResponse, analyze_authorization, BusinessLogicDetector


def test_analyze_authorization_idor_same_body():
    owner = HttpResponse(status=200, body="order id=100 amount=50")
    attacker = HttpResponse(status=200, body="order id=100 amount=50")
    r = analyze_authorization(owner, attacker, resource_id="100")
    assert r["finding_type"] == "idor"


def test_analyze_authorization_owner_no_access():
    owner = HttpResponse(status=403, body="denied")
    attacker = HttpResponse(status=200, body="order id=100")
    r = analyze_authorization(owner, attacker)
    assert r["finding_type"] == "none"


def test_analyze_authorization_access_control_bypass():
    owner = HttpResponse(status=200, body="ok")
    attacker = HttpResponse(status=200, body="ok")
    r = analyze_authorization(owner, attacker, expect_denied=True)
    assert r["finding_type"] == "access_control_bypass"


def test_analyze_authorization_resource_id_leak():
    owner = HttpResponse(status=200, body="order id=100")
    attacker = HttpResponse(status=200, body="you have no access, but here: 100")
    r = analyze_authorization(owner, attacker, resource_id="100")
    assert r["finding_type"] == "idor"


def test_analyze_authorization_no_finding():
    owner = HttpResponse(status=200, body="order id=100")
    attacker = HttpResponse(status=403, body="forbidden")
    r = analyze_authorization(owner, attacker, resource_id="100")
    assert r["finding_type"] == "none"


def test_detector_run_finds_idor():
    # 无 LLM，走确定性兜底差分
    detector = BusinessLogicDetector(llm=None)

    def executor(method, url, role):
        return HttpResponse(status=200, body="secret order 100")  # owner/attacker 相同 → idor

    findings = detector.run("http://t", [{"method": "GET", "url": "/orders/100"}],
                            ["owner", "attacker"], executor)
    assert len(findings) == 1
    assert findings[0]["finding_type"] == "idor"


def test_detector_run_no_executor():
    detector = BusinessLogicDetector(llm=None)
    res = detector.run("http://t", [{"url": "/x"}], ["owner", "attacker"])
    assert res and res[0].get("error")


def test_detector_blocks_ssrf_from_llm():
    # LLM 生成的越界 URL（不同 host）必须被拦截，不交给 executor
    def llm(system, user):
        if "请生成测试用例" in user:
            return [{"method": "GET", "url": "http://169.254.169.254/latest/meta-data",
                     "resource_id": "", "expect_denied": False,
                     "owner": "owner", "attacker": "attacker"}]
        return []

    detector = BusinessLogicDetector(llm=llm)
    calls = []

    def executor(method, url, role):
        calls.append((url, role))
        return HttpResponse(status=200, body="x")

    findings = detector.run("http://target.local", [{"url": "http://target.local/orders/1"}],
                            ["owner", "attacker"], executor)
    assert calls == []  # 越界 URL 未调 executor
    assert any(f["finding_type"] == "blocked" for f in findings)
