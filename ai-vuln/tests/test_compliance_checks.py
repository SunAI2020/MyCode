# -*- coding: utf-8 -*-
"""合规自动评估器测试 — 判定分级与证据可达性

这些用例针对 code-review 查出的漏报缺陷：原有测试只验证了"机制存在"
（能渲染、能返回状态），没验证"结论正确"，因此中危加密缺陷被判『符合』、
两个评估器拿不到证据成为死码，都没被发现。
"""
import pytest

from compliance_checks import (
    check_transport_encryption, check_domestic_adaptation, check_web_security_headers,
)
from compliance_engine import (
    EvidenceBundle, ComplianceControl, build_evidence,
    STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_INSUFFICIENT, MODE_HYBRID,
)


def _ctl(check, evidence_type):
    return ComplianceControl(id='T-01', standard='t', domain='D', category='C',
                             title='T', requirement='R', mode=MODE_HYBRID,
                             check=check, evidence_type=evidence_type)


def _tls(severity, category='弱加密套件'):
    return {'severity': severity, 'category': category, 'title': f'{severity} TLS 问题'}


HTTPS_PORT = [{'host': '10.0.0.1', 'port': 443, 'service': 'https'}]
CTL_TLS = _ctl('check_transport_encryption', 'tls')


# ============================================================
# 传输加密：判定分级
# ============================================================
class TestTransportEncryptionGrading:
    def test_medium_tls_defects_are_not_pass(self):
        """TLS1.0 / RC4 / 3DES 被扫描器普遍评为中危，不得因此判『符合』"""
        ev = EvidenceBundle(target='10.0.0.1', open_ports=HTTPS_PORT,
                            tls_findings=[_tls('MEDIUM', 'TLS 1.0 已启用'),
                                          _tls('MEDIUM', '弱加密套件 RC4'),
                                          _tls('MEDIUM', '弱加密套件 3DES')])
        out = check_transport_encryption(ev, CTL_TLS)
        assert out['status'] == STATUS_PARTIAL
        assert out['status'] != STATUS_PASS
        assert '3 项中危加密配置缺陷' in out['detail']
        assert len(out['evidence']) == 3

    def test_high_tls_defect_is_fail(self):
        """高危加密缺陷说明保密性已无法保证，不是『部分符合』"""
        ev = EvidenceBundle(target='10.0.0.1', open_ports=HTTPS_PORT,
                            tls_findings=[_tls('HIGH', 'SSLv3 已启用')])
        assert check_transport_encryption(ev, CTL_TLS)['status'] == STATUS_FAIL

    def test_high_outranks_medium(self):
        ev = EvidenceBundle(target='10.0.0.1', open_ports=HTTPS_PORT,
                            tls_findings=[_tls('MEDIUM'), _tls('CRITICAL')])
        assert check_transport_encryption(ev, CTL_TLS)['status'] == STATUS_FAIL

    def test_cleartext_port_outranks_tls_defects(self):
        ev = EvidenceBundle(target='10.0.0.1',
                            open_ports=[{'host': '10.0.0.1', 'port': 23, 'service': 'telnet'}],
                            tls_findings=[_tls('MEDIUM')])
        out = check_transport_encryption(ev, CTL_TLS)
        assert out['status'] == STATUS_FAIL
        assert '明文传输服务' in out['detail']

    def test_low_severity_alone_still_passes(self):
        """低危提示不足以推翻符合判定，避免矫枉过正"""
        ev = EvidenceBundle(target='10.0.0.1', open_ports=HTTPS_PORT,
                            tls_findings=[_tls('LOW', '证书有效期偏长')])
        assert check_transport_encryption(ev, CTL_TLS)['status'] == STATUS_PASS

    def test_clean_target_passes(self):
        ev = EvidenceBundle(target='10.0.0.1', open_ports=HTTPS_PORT)
        assert check_transport_encryption(ev, CTL_TLS)['status'] == STATUS_PASS

    def test_no_evidence_is_insufficient(self):
        assert check_transport_encryption(
            EvidenceBundle(target='10.0.0.1'), CTL_TLS)['status'] == STATUS_INSUFFICIENT


# ============================================================
# 证据可达性：评估器必须真能拿到证据
# ============================================================
class TestEvidenceReachability:
    def test_devices_derived_from_ports(self):
        """设备指纹不落库，build_evidence 必须从端口重新推导，
        否则国产化/工控条款永远只能报『证据不足』"""
        rows = [{'host': '10.0.0.1', 'port': 5236, 'protocol': 'tcp',
                 'state': 'open', 'service': 'dm', 'version': '达梦DM8'},
                {'host': '10.0.0.1', 'port': 22, 'protocol': 'tcp',
                 'state': 'open', 'service': 'ssh'}]
        ev = build_evidence(rows, target='10.0.0.1')
        assert ev.devices, '未能从端口推导出设备指纹'
        assert ev.has('device')

    def test_domestic_check_gets_real_verdict(self):
        rows = [{'host': '10.0.0.1', 'port': 5236, 'protocol': 'tcp',
                 'state': 'open', 'service': 'dm', 'version': '达梦DM8'}]
        ev = build_evidence(rows, target='10.0.0.1')
        out = check_domestic_adaptation(ev, _ctl('check_domestic_adaptation', 'device'))
        assert out['status'] != STATUS_INSUFFICIENT, '国产化评估器仍拿不到证据'

    def test_explicit_devices_not_overwritten(self):
        """调用方显式传了设备就不再推导"""
        given = [{'category': 'DOMESTIC_OS', 'vendor': '麒麟', 'product': 'KylinOS'}]
        ev = build_evidence([{'host': '10.0.0.1', 'port': 22, 'service': 'ssh'}],
                            devices=given)
        assert ev.devices == given

    def test_web_findings_flow_into_check(self):
        ev = build_evidence(
            [{'host': '10.0.0.1', 'port': 443, 'service': 'https'}],
            target='10.0.0.1',
            web_findings=[{'severity': 'HIGH', 'category': 'SQL注入',
                           'target': '10.0.0.1'}])
        assert ev.has('web')
        out = check_web_security_headers(ev, _ctl('check_web_security_headers', 'web'))
        assert out['status'] == STATUS_FAIL
        assert 'Web 应用存在 1 个高危' in out['detail']

    def test_web_check_without_evidence_is_insufficient(self):
        """没有 Web 证据时如实报证据不足，不能默认判符合"""
        ev = build_evidence([{'host': '10.0.0.1', 'port': 443, 'service': 'https'}])
        ev.tls_findings = []
        out = check_web_security_headers(ev, _ctl('check_web_security_headers', 'web'))
        assert out['status'] == STATUS_INSUFFICIENT

    def test_no_scan_rows_yields_no_devices(self):
        """无扫描证据时不得凭空造出设备"""
        assert build_evidence(None, target='10.0.0.1').devices == []
