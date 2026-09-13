# -*- coding: utf-8 -*-
"""device_fingerprint 模块单元测试 — 纯逻辑（不依赖网络）"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from device_fingerprint import (
    DeviceFingerprinter, generate_device_findings,
    PORT_SIGNATURES, BANNER_SIGNATURES, PORT_RISK_RULES,
    VENDOR_DEFAULT_CRED_HINTS, CATEGORY_LABELS,
)


def _port(port, service='', product='', version='', state='open'):
    return {'port': port, 'service': service, 'product': product,
            'version': version, 'state': state, 'protocol': 'tcp'}


class TestPortSignatures:
    def test_ot_modbus(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1', [_port(502, service='modbus')])
        assert r['category'] == 'OT'
        assert r['vendor'] == 'Modbus'

    def test_ot_s7comm(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1', [_port(102, service='s7comm')])
        assert r['category'] == 'OT'
        assert r['vendor'] == 'Siemens'

    def test_domestic_dameng(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1', [_port(5236, service='dm')])
        assert r['category'] == 'DOMESTIC_OS'
        assert r['vendor'] == '达梦 DM'

    def test_iot_dahua(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1', [_port(37777, service='dahua')])
        assert r['category'] == 'IOT'
        assert r['vendor'] == '大华'

    def test_iot_printer(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1', [_port(9100, service='jetdirect')])
        assert r['category'] == 'IOT'
        assert r['vendor'] == '打印机'

    def test_network_cisco_smartinstall(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1', [_port(4786, service='tcpwrapped')])
        assert r['category'] == 'NETWORK_DEVICE'
        assert r['vendor'] == 'Cisco'

    def test_generic_port_no_false_positive(self):
        # 普通 SSH 不应被判定为任何专项设备
        r = DeviceFingerprinter().identify_host('10.0.0.1', [_port(22, service='ssh', product='OpenSSH', version='8.9')])
        assert r['category'] is None
        assert r['vendor'] is None


class TestBannerSignatures:
    def test_network_cisco_ios(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(22, service='ssh', product='Cisco IOS', version='15.2')])
        assert r['category'] == 'NETWORK_DEVICE'
        assert r['vendor'] == 'Cisco'

    def test_network_huawei_vrp(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(23, service='telnet', product='Huawei VRP', version='V200R010')])
        assert r['category'] == 'NETWORK_DEVICE'
        assert r['vendor'] == '华为'

    def test_security_fortigate(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(443, service='https', product='FortiGate', version='7.2')])
        assert r['category'] == 'SECURITY_DEVICE'
        assert r['vendor'] == 'Fortinet'

    def test_security_sangfor(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(443, service='https', product='SANGFOR 深信服', version='')])
        assert r['category'] == 'SECURITY_DEVICE'
        assert r['vendor'] == '深信服'

    def test_iot_hikvision(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(80, service='http', product='Hikvision IP Camera', version='V5.6')])
        assert r['category'] == 'IOT'
        assert r['vendor'] == '海康威视'

    def test_ot_simatic(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(80, service='http', product='Siemens SIMATIC', version='S7-1200')])
        assert r['category'] == 'OT'
        assert r['vendor'] == 'Siemens'

    def test_domestic_kingbase(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(5432, service='postgresql', product='KingbaseES', version='V8')])
        assert r['category'] == 'DOMESTIC_OS'
        assert r['vendor'] == '人大金仓'

    def test_domestic_kylin(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(22, service='ssh', product='银河麒麟', version='V10')])
        assert r['category'] == 'DOMESTIC_OS'
        assert r['vendor'] == '麒麟软件'


class TestSrsFR11Vendors:
    """对应《需求规格说明书 v1.1》FR-11 补充的厂商/协议覆盖"""

    def test_security_symantec(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(443, service='https', product='Symantec Endpoint Protection')])
        assert r['category'] == 'SECURITY_DEVICE'
        assert r['vendor'] == '赛门铁克'

    def test_ot_iec61850(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(102, service='mms', product='IEC 61850')])
        assert r['category'] == 'OT'

    def test_ot_profibus(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(80, service='http', product='Profibus DP')])
        assert r['category'] == 'OT'

    def test_domestic_linx(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(22, service='ssh', product='凝思 Linux')])
        assert r['category'] == 'DOMESTIC_OS'
        assert r['vendor'] == '凝思软件'

    def test_domestic_redflag(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(22, service='ssh', product='RedFlag Linux')])
        assert r['category'] == 'DOMESTIC_OS'
        assert r['vendor'] == '红旗软件'

    def test_domestic_newstart(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(22, service='ssh', product='中兴新支点')])
        assert r['category'] == 'DOMESTIC_OS'
        assert r['vendor'] == '中兴'

    def test_domestic_oscar(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(2003, service='oscar', product='神通数据库')])
        assert r['category'] == 'DOMESTIC_OS'
        assert r['vendor'] == '神通'

    def test_domestic_gbase(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1',
            [_port(5258, service='gbase', product='GBase 8a')])
        assert r['category'] == 'DOMESTIC_OS'
        assert r['vendor'] == '南大通用'


class TestIdentifyHost:
    def test_empty_ports_returns_empty_result(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1', [])
        assert r['host'] == '10.0.0.1'
        assert r['category'] is None
        assert r['signals'] == []

    def test_closed_port_ignored(self):
        # closed 状态端口不应参与识别
        r = DeviceFingerprinter().identify_host('10.0.0.1', [_port(502, service='modbus', state='closed')])
        assert r['category'] is None

    def test_higher_confidence_wins(self):
        # 端口 high 置信度 + 横幅 medium 置信度，取 high
        r = DeviceFingerprinter().identify_host('10.0.0.1', [_port(502, service='modbus')])
        assert r['confidence'] == 'high'
        assert r['category'] == 'OT'

    def test_signals_recorded(self):
        r = DeviceFingerprinter().identify_host('10.0.0.1', [_port(502, service='modbus')])
        assert len(r['signals']) >= 1
        assert any('evidence' in s for s in r['signals'])


class TestGenerateDeviceFindings:
    def test_modbus_port_rule_high(self):
        device = DeviceFingerprinter().identify_host('10.0.0.1', [_port(502, service='modbus')])
        findings = generate_device_findings('10.0.0.1', device, [_port(502, service='modbus')])
        assert len(findings) == 1
        assert findings[0]['severity'] == 'HIGH'
        assert 'Modbus' in findings[0]['description']
        assert findings[0]['finding_type'] == 'device'

    def test_vendor_default_cred_hint(self):
        # 海康威视 → 默认口令提示
        device = {'category': 'IOT', 'vendor': '海康威视', 'product': '海康威视摄像头', 'confidence': 'high'}
        findings = generate_device_findings('10.0.0.1', device, [_port(8000, service='http')])
        assert any(f['severity'] == 'MEDIUM' and '默认口令' in f['description'] for f in findings)

    def test_rtsp_rule(self):
        device = {'category': 'IOT', 'vendor': '大华', 'product': '大华摄像头', 'confidence': 'high'}
        findings = generate_device_findings('10.0.0.1', device, [_port(554, service='rtsp')])
        assert any('RTSP' in f['description'] for f in findings)

    def test_finding_structure_aligned(self):
        # finding 必须包含 scan_results 落库所需字段
        device = {'category': 'OT', 'vendor': 'Modbus', 'product': 'Modbus TCP', 'confidence': 'high'}
        f = generate_device_findings('10.0.0.1', device, [_port(502, service='modbus')])[0]
        for key in ('host', 'port', 'protocol', 'service', 'version', 'cve_id',
                    'cvss_score', 'severity', 'description'):
            assert key in f


class TestIdentifyScanResult:
    def test_batch_and_writeback(self):
        fp = DeviceFingerprinter()
        scan_result = {
            'hosts': [
                {'ip': '10.0.0.1', 'status': 'up', 'ports': [_port(502, service='modbus')]},
                {'ip': '10.0.0.2', 'status': 'up', 'ports': [_port(22, service='ssh', product='OpenSSH')]},
                {'ip': '10.0.0.3', 'status': 'down', 'ports': [_port(502, service='modbus')]},
            ]
        }
        devices = fp.identify_scan_result(scan_result)
        assert len(devices) == 1
        assert devices[0]['host'] == '10.0.0.1'
        # 回写 device 字段
        assert scan_result['hosts'][0]['device']['category'] == 'OT'
        assert scan_result['hosts'][1]['device']['category'] is None
        # down 主机不识别
        assert 'device' not in scan_result['hosts'][2]


class TestSignatureDBConsistency:
    def test_all_categories_covered(self):
        categories = set()
        for port, sigs in PORT_SIGNATURES.items():
            for s in sigs:
                categories.add(s['category'])
        for s in BANNER_SIGNATURES:
            categories.add(s['category'])
        assert {'NETWORK_DEVICE', 'SECURITY_DEVICE', 'IOT', 'OT', 'DOMESTIC_OS'} <= categories

    def test_risk_rules_have_required_fields(self):
        for port, rule in PORT_RISK_RULES.items():
            for key in ('severity', 'title', 'description', 'remediation'):
                assert key in rule

    def test_category_labels(self):
        assert CATEGORY_LABELS['IOT'].startswith('物联网设备')
        assert CATEGORY_LABELS['DOMESTIC_OS'].startswith('国产化系统')
