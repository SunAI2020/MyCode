"""
漏洞匹配引擎测试
"""
import unittest
import tempfile
from pathlib import Path

from database import VulnerabilityDatabase, CVE, Severity, ScannedService
from scanner import VulnerabilityMatcher, VersionMatcher


class TestVersionMatcher(unittest.TestCase):
    """版本匹配器测试"""
    
    def test_parse_version(self):
        """测试版本解析"""
        self.assertEqual(VersionMatcher.parse_version("1.2.3"), (1, 2, 3))
        self.assertEqual(VersionMatcher.parse_version("1.0"), (1, 0))
        self.assertEqual(VersionMatcher.parse_version("1"), (1,))
        self.assertEqual(VersionMatcher.parse_version(""), (0,))
        self.assertEqual(VersionMatcher.parse_version("abc"), (0,))
        self.assertEqual(VersionMatcher.parse_version("1.2.3-beta"), (1, 2, 3))
    
    def test_version_in_range(self):
        """测试版本范围检查"""
        affected = ["1.0", "1.1", "1.2", "2.0"]
        
        self.assertTrue(VersionMatcher.version_in_range("1.0", affected))
        self.assertTrue(VersionMatcher.version_in_range("1.1", affected))
        self.assertTrue(VersionMatcher.version_in_range("2.0", affected))
        self.assertFalse(VersionMatcher.version_in_range("3.0", affected))
        self.assertFalse(VersionMatcher.version_in_range("", affected))
        self.assertFalse(VersionMatcher.version_in_range("1.0", []))
    
    def test_product_match(self):
        """测试产品匹配"""
        cve_products = ["Apache HTTP Server", "Nginx", "OpenSSH"]
        
        self.assertEqual(
            VersionMatcher.product_match("Apache HTTP Server", cve_products),
            "Apache HTTP Server"
        )
        self.assertEqual(
            VersionMatcher.product_match("apache", cve_products),
            "Apache HTTP Server"
        )
        self.assertEqual(
            VersionMatcher.product_match("nginx", cve_products),
            "Nginx"
        )
        self.assertEqual(
            VersionMatcher.product_match("ssh", cve_products),
            "OpenSSH"
        )
        self.assertIsNone(VersionMatcher.product_match("IIS", cve_products))


class TestVulnerabilityMatcher(unittest.TestCase):
    """漏洞匹配引擎测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db = VulnerabilityDatabase(self.temp_db.name)
        self.matcher = VulnerabilityMatcher(self.db)
        
        # 添加测试 CVE
        cve = CVE(
            cve_id="CVE-2021-MATCH-TEST",
            name="OpenSSH Test Vulnerability",
            description="Test vulnerability for OpenSSH",
            affected_products=["OpenSSH"],
            affected_versions=["7.0", "7.1", "7.2", "7.3", "7.4"],
            cvss_score=8.5,
            severity=Severity.HIGH,
            published_date="2021-01-01",
            modified_date="2021-01-02",
            references=[],
            fix_recommendation="Upgrade to 7.5+"
        )
        self.db.add_cve(cve)
    
    def tearDown(self):
        """测试后清理"""
        Path(self.temp_db.name).unlink(missing_ok=True)
    
    def test_match_service(self):
        """测试服务漏洞匹配"""
        service = ScannedService(
            host_ip="192.168.1.1",
            port=22,
            protocol="tcp",
            service_name="ssh",
            product="OpenSSH",
            version="7.2",
            extra_info="",
            banner="SSH-2.0-OpenSSH_7.2"
        )
        
        vulns = self.matcher.match_service(service)
        
        self.assertEqual(len(vulns), 1)
        self.assertEqual(vulns[0].cve.cve_id, "CVE-2021-MATCH-TEST")
        self.assertEqual(vulns[0].host_ip, "192.168.1.1")
        self.assertEqual(vulns[0].port, 22)
    
    def test_match_service_no_match(self):
        """测试无匹配情况"""
        service = ScannedService(
            host_ip="192.168.1.1",
            port=80,
            protocol="tcp",
            service_name="http",
            product="Apache",
            version="2.4.41",
            extra_info="",
            banner=""
        )
        
        vulns = self.matcher.match_service(service)
        self.assertEqual(len(vulns), 0)
    
    def test_match_all_services(self):
        """测试批量服务匹配"""
        services = [
            ScannedService(
                host_ip="192.168.1.1",
                port=22,
                protocol="tcp",
                service_name="ssh",
                product="OpenSSH",
                version="7.2",
            ),
            ScannedService(
                host_ip="192.168.1.1",
                port=80,
                protocol="tcp",
                service_name="http",
                product="Apache",
                version="2.4.41",
            ),
        ]
        
        vulns = self.matcher.match_all_services(services)
        self.assertEqual(len(vulns), 1)
    
    def test_get_statistics(self):
        """测试统计信息"""
        cve_critical = CVE(
            cve_id="CVE-2021-CRITICAL",
            name="Critical Test",
            description="Test",
            affected_products=["Test"],
            affected_versions=["1.0"],
            cvss_score=9.8,
            severity=Severity.CRITICAL,
            published_date="2021-01-01",
            modified_date="2021-01-02",
            references=[],
            fix_recommendation="Upgrade",
            exploit_available=True
        )
        self.db.add_cve(cve_critical)
        
        from database import FoundVulnerability
        
        vulns = [
            FoundVulnerability(
                cve=self.db.get_cve("CVE-2021-MATCH-TEST"),
                host_ip="192.168.1.1",
                port=22,
                service="ssh",
                matched_version="7.2",
                confidence="high"
            ),
            FoundVulnerability(
                cve=cve_critical,
                host_ip="192.168.1.1",
                port=22,
                service="ssh",
                matched_version="7.2",
                confidence="high"
            ),
        ]
        
        stats = self.matcher.get_statistics(vulns)
        
        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['critical_count'], 1)
        self.assertEqual(stats['high_count'], 1)
        self.assertEqual(stats['exploitable_count'], 1)
    
    def test_false_positive(self):
        """测试误报标记"""
        service = ScannedService(
            host_ip="192.168.1.1",
            port=22,
            protocol="tcp",
            service_name="ssh",
            product="OpenSSH",
            version="7.2",
        )
        
        # 第一次匹配
        vulns = self.matcher.match_service(service)
        self.assertEqual(len(vulns), 1)
        
        # 标记为误报
        self.matcher.mark_false_positive(vulns[0])
        
        # 第二次匹配应该返回空
        vulns = self.matcher.match_service(service)
        self.assertEqual(len(vulns), 0)


if __name__ == '__main__':
    unittest.main()
