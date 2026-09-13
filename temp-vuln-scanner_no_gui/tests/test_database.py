"""
数据库模块测试
"""
import unittest
import tempfile
import json
from pathlib import Path

from database import VulnerabilityDatabase, CVE, Severity


class TestVulnerabilityDatabase(unittest.TestCase):
    """漏洞数据库测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db = VulnerabilityDatabase(self.temp_db.name)
    
    def tearDown(self):
        """测试后清理"""
        Path(self.temp_db.name).unlink(missing_ok=True)
    
    def test_add_cve(self):
        """测试添加 CVE"""
        cve = CVE(
            cve_id="CVE-2021-TEST",
            name="Test Vulnerability",
            description="Test description",
            affected_products=["Test Product"],
            affected_versions=["1.0", "2.0"],
            cvss_score=9.8,
            severity=Severity.CRITICAL,
            published_date="2021-01-01",
            modified_date="2021-01-02",
            references=["https://example.com"],
            fix_recommendation="Upgrade to latest version"
        )
        
        result = self.db.add_cve(cve)
        self.assertTrue(result)
    
    def test_get_cve(self):
        """测试查询 CVE"""
        cve = CVE(
            cve_id="CVE-2021-TEST2",
            name="Test Vulnerability 2",
            description="Test description 2",
            affected_products=["Test Product 2"],
            affected_versions=["1.0"],
            cvss_score=7.5,
            severity=Severity.HIGH,
            published_date="2021-02-01",
            modified_date="2021-02-02",
            references=[],
            fix_recommendation="Patch available"
        )
        
        self.db.add_cve(cve)
        retrieved = self.db.get_cve("CVE-2021-TEST2")
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.cve_id, "CVE-2021-TEST2")
        self.assertEqual(retrieved.cvss_score, 7.5)
    
    def test_search_vulnerabilities(self):
        """测试搜索漏洞"""
        # 添加测试数据
        for i in range(5):
            cve = CVE(
                cve_id=f"CVE-2021-00{i}",
                name=f"Test Vulnerability {i}",
                description=f"Test description {i}",
                affected_products=["Apache", "Nginx"],
                affected_versions=["1.0", "2.0"],
                cvss_score=9.0 - i,
                severity=Severity.CRITICAL if i < 2 else Severity.HIGH,
                published_date="2021-01-01",
                modified_date="2021-01-02",
                references=[],
                fix_recommendation="Upgrade"
            )
            self.db.add_cve(cve)
        
        # 按产品搜索
        results = self.db.search_vulnerabilities(product="Apache", limit=10)
        self.assertEqual(len(results), 5)
        
        # 按严重程度搜索
        results = self.db.search_vulnerabilities(severity=Severity.CRITICAL, limit=10)
        self.assertEqual(len(results), 2)
        
        # 按 CVSS 分数搜索
        results = self.db.search_vulnerabilities(min_cvss=8.0, limit=10)
        self.assertEqual(len(results), 2)
    
    def test_match_vulnerability(self):
        """测试漏洞匹配"""
        cve = CVE(
            cve_id="CVE-2021-MATCH",
            name="Match Test",
            description="Test",
            affected_products=["OpenSSH"],
            affected_versions=["7.0", "7.1", "7.2"],
            cvss_score=8.5,
            severity=Severity.HIGH,
            published_date="2021-01-01",
            modified_date="2021-01-02",
            references=[],
            fix_recommendation="Upgrade"
        )
        self.db.add_cve(cve)
        
        results = self.db.match_vulnerability("OpenSSH", "7.1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].cve_id, "CVE-2021-MATCH")
    
    def test_statistics(self):
        """测试统计信息"""
        # 添加测试数据
        for i in range(10):
            cve = CVE(
                cve_id=f"CVE-2021-STAT{i}",
                name=f"Stat Test {i}",
                description="Test",
                affected_products=["Test"],
                affected_versions=["1.0"],
                cvss_score=5.0 + i * 0.5,
                severity=Severity.HIGH if i < 5 else Severity.MEDIUM,
                published_date="2021-01-01",
                modified_date="2021-01-02",
                references=[],
                fix_recommendation="Upgrade"
            )
            self.db.add_cve(cve)
        
        stats = self.db.get_statistics()
        
        self.assertEqual(stats['total_cves'], 10)
        self.assertIn('HIGH', stats['by_severity'])
        self.assertIn('MEDIUM', stats['by_severity'])
    
    def test_load_from_json(self):
        """测试从 JSON 加载"""
        # 创建测试 JSON 文件
        test_data = [
            {
                "cve_id": "CVE-2021-JSON1",
                "name": "JSON Test 1",
                "description": "Test",
                "affected_products": ["Test"],
                "affected_versions": ["1.0"],
                "cvss_score": 9.0,
                "severity": "CRITICAL",
                "published_date": "2021-01-01",
                "modified_date": "2021-01-02",
                "references": [],
                "fix_recommendation": "Upgrade"
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            json_path = f.name
        
        try:
            count = self.db.load_from_json(json_path)
            self.assertEqual(count, 1)
            
            cve = self.db.get_cve("CVE-2021-JSON1")
            self.assertIsNotNone(cve)
        finally:
            Path(json_path).unlink(missing_ok=True)
    
    def test_export_to_json(self):
        """测试导出到 JSON"""
        # 添加测试数据
        cve = CVE(
            cve_id="CVE-2021-EXPORT",
            name="Export Test",
            description="Test",
            affected_products=["Test"],
            affected_versions=["1.0"],
            cvss_score=9.0,
            severity=Severity.CRITICAL,
            published_date="2021-01-01",
            modified_date="2021-01-02",
            references=[],
            fix_recommendation="Upgrade"
        )
        self.db.add_cve(cve)
        
        # 导出
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            output_path = f.name
        
        try:
            count = self.db.export_to_json(output_path)
            self.assertEqual(count, 1)
            
            with open(output_path, 'r') as f:
                data = json.load(f)
            
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]['cve_id'], "CVE-2021-EXPORT")
        finally:
            Path(output_path).unlink(missing_ok=True)


class TestCVEModel(unittest.TestCase):
    """CVE 模型测试"""
    
    def test_cve_to_dict(self):
        """测试 CVE 转字典"""
        cve = CVE(
            cve_id="CVE-2021-DICT",
            name="Dict Test",
            description="Test",
            affected_products=["Test"],
            affected_versions=["1.0"],
            cvss_score=9.0,
            severity=Severity.CRITICAL,
            published_date="2021-01-01",
            modified_date="2021-01-02",
            references=["https://example.com"],
            fix_recommendation="Upgrade"
        )
        
        data = cve.to_dict()
        
        self.assertEqual(data['cve_id'], "CVE-2021-DICT")
        self.assertEqual(data['severity'], "CRITICAL")
        self.assertEqual(data['cvss_score'], 9.0)
    
    def test_cve_from_dict(self):
        """测试从字典创建 CVE"""
        data = {
            "cve_id": "CVE-2021-FROMDICT",
            "name": "From Dict Test",
            "description": "Test",
            "affected_products": ["Test"],
            "affected_versions": ["1.0"],
            "cvss_score": 7.5,
            "severity": "HIGH",
            "published_date": "2021-01-01",
            "modified_date": "2021-01-02",
            "references": [],
            "fix_recommendation": "Patch"
        }
        
        cve = CVE.from_dict(data)
        
        self.assertEqual(cve.cve_id, "CVE-2021-FROMDICT")
        self.assertEqual(cve.severity, Severity.HIGH)
        self.assertEqual(cve.cvss_score, 7.5)


if __name__ == '__main__':
    unittest.main()
