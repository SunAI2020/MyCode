"""
AI-PTS 扫描器集成模块
整合vuln-scanner的扫描功能
"""
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict

# 添加vuln-scanner路径
VULN_SCANNER_PATH = Path(__file__).parent.parent / "vuln-scanner"
if str(VULN_SCANNER_PATH) not in sys.path:
    sys.path.insert(0, str(VULN_SCANNER_PATH))

# 导出vuln-scanner模块
from vuln_scanner.core.engine import ScanEngine, create_engine
from vuln_scanner.scanner.nmap_scanner import NmapScanner, create_scanner
from vuln_scanner.scanner.vuln_matcher import VulnMatcher, create_matcher
from vuln_scanner.database.vuln_database import VulnerabilityDatabase
from vuln_scanner.database.models import (
    ScanResult, ScannedHost, ScannedService, FoundVulnerability,
    Severity
)

# 数据模型适配 - 转换为AI-PTS格式
def to_ai_service(scanned_service: ScannedService):
    """转换为AI分析用的服务格式"""
    from aipts.core.ai_analyzer import ScannedService as AIService

    return AIService(
        host_ip=scanned_service.host_ip,
        port=scanned_service.port,
        protocol=scanned_service.protocol,
        service_name=scanned_service.service_name,
        product=scanned_service.product,
        version=scanned_service.version,
        banner=scanned_service.banner
    )


def to_ai_vulnerability(found_vuln: FoundVulnerability):
    """转换为AI分析用的漏洞格式"""
    from aipts.core.ai_analyzer import Vulnerability as AIVuln

    return AIVuln(
        cve_id=found_vuln.cve_id,
        description=found_vuln.description,
        severity=found_vuln.severity.value if found_vuln.severity else "medium",
        cvss_score=found_vuln.cvss_score,
        product=found_vuln.product,
        version=found_vuln.affected_version or ""
    )


class PTScanner:
    """AI-PTS扫描器封装"""

    def __init__(self, db_path: str = None):
        """
        初始化扫描器

        Args:
            db_path: 漏洞数据库路径
        """
        self.engine = create_engine(
            db_path=db_path,
            output_dir=str(Path(__file__).parent.parent / "reports")
        )
        self.last_result: Optional[ScanResult] = None

    def initialize_database(self, cve_data_path: str = None) -> Dict:
        """
        初始化漏洞数据库

        Args:
            cve_data_path: CVE JSON数据路径

        Returns:
            Dict: 统计信息
        """
        return self.engine.initialize_database(cve_data_path)

    def scan(
        self,
        target: str,
        ports: str = None,
        version_detect: bool = True,
        os_detect: bool = False
    ) -> ScanResult:
        """
        执行扫描

        Args:
            target: 扫描目标
            ports: 端口范围
            version_detect: 版本检测
            os_detect: OS检测

        Returns:
            ScanResult: 扫描结果
        """
        self.last_result = self.engine.scan_sync(
            target=target,
            ports=ports,
            version_detect=version_detect,
            os_detect=os_detect
        )
        return self.last_result

    def match_vulnerabilities(
        self,
        services: List[ScannedService] = None
    ) -> List[FoundVulnerability]:
        """
        匹配漏洞

        Args:
            services: 服务列表，None则使用扫描结果

        Returns:
            List[FoundVulnerability]: 漏洞列表
        """
        if services is None:
            services = self.last_result.services if self.last_result else []

        return self.engine.matcher.match_all_services(services)

    def get_ai_services(self) -> List:
        """获取AI分析用的服务列表"""
        if not self.last_result:
            return []

        return [to_ai_service(s) for s in self.last_result.services]

    def get_ai_vulnerabilities(self) -> List:
        """获取AI分析用的漏洞列表"""
        vulns = self.match_vulnerabilities()
        return [to_ai_vulnerability(v) for v in vulns]

    def search_vulns(
        self,
        product: str = None,
        severity: str = None,
        min_cvss: float = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        搜索漏洞

        Args:
            product: 产品名称
            severity: 严重程度
            min_cvss: 最小CVSS分数
            limit: 返回数量

        Returns:
            List[Dict]: 漏洞列表
        """
        return self.engine.search_vulns(
            product=product,
            severity=severity,
            min_cvss=min_cvss,
            limit=limit
        )

    def get_statistics(self) -> Dict:
        """获取漏洞库统计"""
        return self.engine.get_vuln_stats()

    def export_db(self, output_path: str, limit: int = None) -> int:
        """
        导出漏洞数据库

        Args:
            output_path: 输出路径
            limit: 导出数量

        Returns:
            int: 导出数量
        """
        return self.engine.export_vuln_db(output_path, limit)


def create_scanner_instance(db_path: str = None) -> PTScanner:
    """创建扫描器实例"""
    return PTScanner(db_path=db_path)


# 导入漏洞库数据
def import_cve_data(json_path: str = None, db_path: str = None) -> int:
    """
    导入CVE数据到漏洞库

    Args:
        json_path: CVE JSON文件路径
        db_path: 数据库路径

    Returns:
        int: 导入数量
    """
    scanner = PTScanner(db_path=db_path)
    return scanner.initialize_database(json_path)


__all__ = [
    "PTScanner",
    "create_scanner_instance",
    "import_cve_data",
    "ScanResult",
    "ScannedHost",
    "ScannedService",
    "FoundVulnerability",
    "to_ai_service",
    "to_ai_vulnerability"
]