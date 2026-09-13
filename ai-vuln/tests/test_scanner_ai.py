# -*- coding: utf-8 -*-
"""扫描引擎 + AI分析器核心逻辑测试"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestNetworkScannerParsing:
    @pytest.fixture
    def scanner(self, db):
        from scanner_engine import NetworkScanner
        return NetworkScanner(db=db)

    def test_parse_target_single_ip(self, scanner):
        assert scanner.parse_target('192.168.1.1') == ['192.168.1.1']

    def test_parse_target_range(self, scanner):
        assert scanner.parse_target('192.168.1.1-3') == [
            '192.168.1.1', '192.168.1.2', '192.168.1.3']

    def test_parse_target_cidr(self, scanner):
        assert len(scanner.parse_target('10.0.0.0/30')) >= 2

    def test_parse_target_cidr_32_single_host(self, scanner):
        assert scanner.parse_target('10.0.0.5/32') == ['10.0.0.5']

    def test_parse_target_cidr_31_point_to_point(self, scanner):
        assert len(scanner.parse_target('10.0.0.0/31')) == 2

    def test_parse_target_hostname(self, scanner):
        assert scanner.parse_target('localhost') == ['localhost']

    def test_common_ports(self, scanner):
        assert scanner.COMMON_PORTS[22] == 'ssh'
        assert scanner.COMMON_PORTS[80] == 'http'
        assert scanner.COMMON_PORTS[443] == 'https'
        assert scanner.COMMON_PORTS[3306] == 'mysql'
        assert scanner.COMMON_PORTS[5432] == 'postgresql'

    def test_service_fingerprints(self, scanner):
        assert b'SSH-' in scanner.SERVICE_FINGERPRINTS['ssh']
        assert b'HTTP/' in scanner.SERVICE_FINGERPRINTS['http']

    def test_custom_timeout(self, db):
        from scanner_engine import NetworkScanner
        assert NetworkScanner(db=db, timeout=10).timeout == 10
        assert NetworkScanner(db=db).timeout == 5


class TestAIAnalyzerPatterns:
    @pytest.fixture
    def analyzer(self):
        from ai_analyzer import AIAnalyzer
        return AIAnalyzer()

    def _cat_issues(self, issues, category):
        return [i for i in issues if i['category'] == category]

    def test_sql_fstring_detected(self, analyzer):
        code = 'cursor.execute(f"SELECT * FROM users WHERE id={uid}")'
        assert len(self._cat_issues(analyzer.analyze_code(code, 't.py'), 'SQL注入')) >= 1

    def test_sql_concat_detected(self, analyzer):
        code = 'cursor.execute("SELECT * FROM users WHERE name=\'" + u + "\'")'
        assert len(self._cat_issues(analyzer.analyze_code(code, 't.py'), 'SQL注入')) >= 1

    def test_safe_param_query_clean(self, analyzer):
        code = 'cursor.execute("SELECT * FROM users WHERE id=?", (uid,))'
        assert len(self._cat_issues(analyzer.analyze_code(code, 't.py'), 'SQL注入')) == 0

    def test_command_injection_detected(self, analyzer):
        code = 'os.system("rm -rf " + u)'
        assert len(self._cat_issues(analyzer.analyze_code(code, 't.py'), '命令注入')) >= 1

    def test_eval_detected(self, analyzer):
        code = 'eval(user_input)'
        assert len(self._cat_issues(analyzer.analyze_code(code, 't.py'), '命令注入')) >= 1

    def test_hardcoded_key_detected(self, analyzer):
        code = 'API_KEY = "sk-1234567890abcdef1234567890abcdef"'
        assert len(self._cat_issues(analyzer.analyze_code(code, 't.py'), '硬编码密钥')) >= 1

    def test_hardcoded_password_detected(self, analyzer):
        code = 'password = "admin123456"'
        assert len(self._cat_issues(analyzer.analyze_code(code, 't.py'), '硬编码密钥')) >= 1

    def test_pickle_detected(self, analyzer):
        code = 'data = pickle.loads(user_input)'
        assert len(self._cat_issues(analyzer.analyze_code(code, 't.py'), '不安全的反序列化')) >= 1

    def test_md5_detected(self, analyzer):
        code = 'hash = hashlib.md5(data).hexdigest()'
        assert len(self._cat_issues(analyzer.analyze_code(code, 't.py'), '弱加密算法')) >= 1

    def test_clean_code_no_issues(self, analyzer):
        code = 'def add(a, b):\n    return a + b\nresult = add(1, 2)'
        assert len(analyzer.analyze_code(code, 'test.py')) == 0

    def test_severity_map(self, analyzer):
        assert analyzer.SEVERITY_MAP['SQL注入'] == 'CRITICAL'
        assert analyzer.SEVERITY_MAP['命令注入'] == 'CRITICAL'
        assert analyzer.SEVERITY_MAP['弱加密算法'] == 'MEDIUM'
        assert analyzer.SEVERITY_MAP['信息泄露'] == 'LOW'

    def test_xss_innerhtml_detected(self, analyzer):
        code = 'document.getElementById("x").innerHTML = u'
        assert len(self._cat_issues(analyzer.analyze_code(code, 't.js'), 'XSS漏洞')) >= 1

    def test_path_traversal_detected(self, analyzer):
        code = 'open("../../etc/passwd" + p)'
        assert len(self._cat_issues(analyzer.analyze_code(code, 't.py'), '路径遍历')) >= 1

    def test_ssrf_detected(self, analyzer):
        code = 'requests.get(user_input_url)'
        assert len(self._cat_issues(analyzer.analyze_code(code, 't.py'), 'SSRF漏洞')) >= 1
