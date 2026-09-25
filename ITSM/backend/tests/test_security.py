"""脱敏工具单测。"""
from app.core.security import mask_sensitive, masked_page


def test_mask_sensitive_customer_scope():
    data = {"contact": "13812345678", "ip": "10.1.2.3", "amount": 120000.0}
    out = mask_sensitive(data, scope=1)
    assert out["contact"] == "138****5678"
    assert out["ip"] == "10.1.*.*"
    assert out["amount"] == "***"


def test_mask_sensitive_platform_no_mask():
    data = {"contact": "13812345678", "ip": "10.1.2.3", "amount": 120000.0}
    out = mask_sensitive(data, scope=None)
    assert out["contact"] == "13812345678"
    assert out["ip"] == "10.1.2.3"
    assert out["amount"] == 120000.0


def test_masked_page():
    result = {"items": [{"ip": "10.1.2.3"}, {"ip": "192.168.1.1"}], "total": 2}
    out = masked_page(result, scope=1)
    assert out["items"][0]["ip"] == "10.1.*.*"
    assert out["items"][1]["ip"] == "192.168.*.*"
