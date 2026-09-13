# -*- coding: utf-8 -*-
"""多因子风险评分测试"""
from risk_scoring import RiskScorer, risk_level, threat_factor, vulnerability_factor, asset_value_factor, exposure_factor


def test_kev_dominates_threat():
    v = {'cve_id': 'CVE-X', 'kev': True, 'cvss_score': 9.8, 'severity': 'CRITICAL'}
    assert threat_factor(v) == 1.0


def test_epss_fallback():
    v = {'cve_id': 'CVE-X', 'epss_score': 0.42, 'severity': 'HIGH'}
    assert abs(threat_factor(v) - 0.42) < 1e-9


def test_vulnerability_factor_cvss():
    v = {'cvss_score': 9.0}
    assert abs(vulnerability_factor(v) - 0.9) < 1e-9


def test_score_multiplicative_critical_asset():
    s = RiskScorer()
    v = {'kev': True, 'cvss_score': 10.0, 'severity': 'CRITICAL'}
    r = s.score(v, asset_importance='CRITICAL')
    assert r['risk_score'] == 100
    assert r['risk_level'] == 'CRITICAL'


def test_score_low_risk():
    s = RiskScorer()
    v = {'cvss_score': 2.0, 'severity': 'LOW'}
    r = s.score(v, asset_importance='LOW')
    assert r['risk_level'] in ('LOW', 'INFO')
    assert r['risk_score'] < 40


def test_risk_level_boundaries():
    assert risk_level(100) == 'CRITICAL'
    assert risk_level(80) == 'CRITICAL'
    assert risk_level(60) == 'HIGH'
    assert risk_level(40) == 'MEDIUM'
    assert risk_level(20) == 'LOW'
    assert risk_level(0) == 'INFO'


def test_asset_value_factor_default():
    assert asset_value_factor('HIGH') == 0.8
    assert asset_value_factor(None) == 0.6


def test_score_many_annotates():
    s = RiskScorer()
    out = s.score_many([{'cvss_score': 9.0}, {'cvss_score': 3.0}], 'MEDIUM')
    assert 'risk_score' in out[0] and 'risk_level' in out[0]
    assert out[0]['risk_score'] >= out[1]['risk_score']


def test_zero_epss_not_fallback():
    v = {'epss_score': 0.0, 'severity': 'HIGH'}
    assert threat_factor(v) == 0.0


def test_zero_cvss_not_fallback():
    v = {'cvss_score': 0.0, 'severity': 'HIGH'}
    assert vulnerability_factor(v) == 0.0


# ===== 暴露面/可达性系数（对标 Wiz 可达性优先）=====

def test_exposure_factor_default_neutral():
    # 无 host/state/exposure → 默认 1.0，不惩罚（向后兼容）
    assert exposure_factor({'cvss_score': 9.0}) == 1.0


def test_exposure_factor_closed_port_unreachable():
    assert exposure_factor({'state': 'closed'}) == 0.1
    assert exposure_factor({'state': 'filtered'}) == 0.1


def test_exposure_factor_public_host():
    assert exposure_factor({'host': '8.8.8.8'}) == 1.0


def test_exposure_factor_private_host():
    assert exposure_factor({'host': '192.168.1.10'}) == 0.7
    assert exposure_factor({'host': '10.0.0.5'}) == 0.7
    assert exposure_factor({'host': '172.16.0.1'}) == 0.7


def test_exposure_factor_loopback():
    assert exposure_factor({'host': '127.0.0.1'}) == 0.3


def test_exposure_factor_hostname_neutral():
    assert exposure_factor({'host': 'example.com'}) == 1.0


def test_exposure_factor_explicit_override():
    assert exposure_factor({'exposure': 0.5}) == 0.5
    # 显式覆盖优先于 host/state
    assert exposure_factor({'exposure': 0.9, 'host': '127.0.0.1', 'state': 'closed'}) == 0.9


def test_exposure_factor_clamped():
    assert exposure_factor({'exposure': 1.5}) == 1.0
    assert exposure_factor({'exposure': -0.2}) == 0.0


def test_score_private_host_lower_than_public():
    s = RiskScorer()
    base = {'kev': True, 'cvss_score': 10.0, 'severity': 'CRITICAL'}
    pub = s.score({**base, 'host': '8.8.8.8'}, 'CRITICAL')
    priv = s.score({**base, 'host': '192.168.1.10'}, 'CRITICAL')
    assert pub['risk_score'] > priv['risk_score']
    assert priv['factors']['exposure'] == 0.7


def test_score_closed_port_reduces():
    s = RiskScorer()
    open_v = s.score({'kev': True, 'cvss_score': 10.0, 'state': 'open'}, 'CRITICAL')
    closed_v = s.score({'kev': True, 'cvss_score': 10.0, 'state': 'closed'}, 'CRITICAL')
    assert closed_v['risk_score'] < open_v['risk_score']
