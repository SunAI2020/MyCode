# -*- coding: utf-8 -*-
"""honeypot_detector 模块单元测试 — 纯逻辑（不依赖网络）"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from honeypot_detector import (
    HoneypotDetector, generate_honeypot_findings,
    HONEYPOT_SIGNATURES, HONEYPOT_PORT_SIGNATURES,
)


def _port(port, service='', product='', version='', state='open'):
    return {'port': port, 'service': service, 'product': product,
            'version': version, 'state': state, 'protocol': 'tcp'}


class TestBannerSignatures:
    def test_cowrie_ssh_default_banner(self):
        r = HoneypotDetector().detect_host('10.0.0.1',
            [_port(22, service='ssh', product='openssh',
                   version='SSH-2.0-OpenSSH_6.0p1 Debian-4+deb7u2')])
        assert r['is_honeypot'] is True
        assert r['type'] == 'Cowrie'
        assert r['confidence'] == 'P1'

    def test_clean_openssh_not_flagged(self):
        # 真实 OpenSSH 不应被判定为蜜罐
        r = HoneypotDetector().detect_host('10.0.0.1',
            [_port(22, service='ssh', product='OpenSSH', version='8.9p1')])
        assert r['is_honeypot'] is False
        assert r['type'] is None


class TestPortComboSignatures:
    def test_honeyd_port_combo(self):
        r = HoneypotDetector().detect_host('10.0.0.1',
            [_port(p, service='unknown') for p in (22, 80, 443, 21, 25)])
        assert r['is_honeypot'] is True
        assert r['type'] == 'Honeyd'

    def test_normal_host_single_service(self):
        # 仅开放一个常见端口的正常主机不应命中服务组合
        r = HoneypotDetector().detect_host('10.0.0.1',
            [_port(443, service='https', product='nginx', version='1.24.0')])
        assert r['is_honeypot'] is False


class TestWeakSignal:
    def test_p2_signal_recorded_but_not_flagged(self):
        # P2 弱信号（banner 类）：只记录 evidence，不标记 is_honeypot
        r = HoneypotDetector().detect_host('10.0.0.1',
            [_port(80, service='http', product='dionaea', version='python/2.7')])
        assert r['is_honeypot'] is False
        assert r['signals']  # 仍记录证据供 AI 二次判断
        assert r['confidence'] == 'P2'

    def test_http_field_signature_skipped(self):
        # http_title/http_body 签名需带 IO 探测，纯数据阶段跳过（不误匹配 banner）
        r = HoneypotDetector().detect_host('10.0.0.1',
            [_port(80, service='http', product='conpot', version='')])
        assert r['is_honeypot'] is False


class TestDetectHost:
    def test_empty_ports(self):
        r = HoneypotDetector().detect_host('10.0.0.1', [])
        assert r['host'] == '10.0.0.1'
        assert r['is_honeypot'] is False
        assert r['signals'] == []

    def test_closed_port_ignored(self):
        # closed 状态端口不应参与识别
        r = HoneypotDetector().detect_host('10.0.0.1',
            [_port(22, service='ssh', version='SSH-2.0-OpenSSH_6.0p1 Debian-4+deb7u2', state='closed')])
        assert r['is_honeypot'] is False


class TestGenerateFindings:
    def test_finding_structure_aligned(self):
        # finding 必须包含 scan_results 落库所需字段
        hp = {'host': '10.0.0.1', 'is_honeypot': True, 'type': 'Cowrie',
              'confidence': 'P1', 'signals': [{'honeypot': 'Cowrie', 'confidence': 'P1',
                                               'evidence': '横幅: x'}]}
        f = generate_honeypot_findings('10.0.0.1', hp, [])[0]
        for key in ('host', 'port', 'protocol', 'service', 'version', 'cve_id',
                    'cvss_score', 'severity', 'description'):
            assert key in f
        assert f['finding_type'] == 'honeypot'
        assert f['honeypot_type'] == 'Cowrie'
        assert f['cve_id'] is None
        assert f['severity'] == 'MEDIUM'
        assert '蜜罐' in f['description']


class TestDetectScanResult:
    def test_batch_and_writeback(self):
        det = HoneypotDetector()
        scan_result = {
            'hosts': [
                {'ip': '10.0.0.1', 'status': 'up', 'ports': [
                    _port(22, service='ssh', product='openssh',
                          version='SSH-2.0-OpenSSH_6.0p1 Debian-4+deb7u2')]},
                {'ip': '10.0.0.2', 'status': 'up', 'ports': [
                    _port(443, service='https', product='nginx')]},
                {'ip': '10.0.0.3', 'status': 'down', 'ports': [
                    _port(22, service='ssh', version='SSH-2.0-OpenSSH_6.0p1 Debian-4+deb7u2')]},
            ]
        }
        hits = det.detect_scan_result(scan_result)
        assert len(hits) == 1
        assert hits[0]['host'] == '10.0.0.1'
        # 回写 honeypot 字段
        assert scan_result['hosts'][0]['honeypot']['is_honeypot'] is True
        assert scan_result['hosts'][1]['honeypot']['is_honeypot'] is False
        # down 主机不识别
        assert 'honeypot' not in scan_result['hosts'][2]


class TestSignatureDBConsistency:
    def test_signatures_have_required_fields(self):
        for sig in HONEYPOT_SIGNATURES:
            for key in ('honeypot', 'protocol', 'field', 'pattern', 'confidence'):
                assert key in sig

    def test_confidence_values_valid(self):
        valid = {'P0', 'P1', 'P2'}
        for sig in HONEYPOT_SIGNATURES:
            assert sig['confidence'] in valid

    def test_port_combo_signatures_non_empty(self):
        for name, portset in HONEYPOT_PORT_SIGNATURES.items():
            assert len(portset) >= 3
            assert all(isinstance(p, int) for p in portset)
