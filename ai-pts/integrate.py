"""
AI-PTS 扫描器集成模块

封装自包含扫描引擎（core.scanner，底层为 vendored 的 ai-vuln 扫描模块），
替代旧的 `vuln_scanner` 幻影包，实现无兄弟项目引用的自包含集成。
"""
from typing import List, Dict, Optional

from core.scanner import (
    ScanEngine,
    ScanResult,
    ScannedHost,
    ScannedService,
    create_engine,
    create_scanner,
)
from core.ai_analyzer import ScannedService as AIService, Vulnerability as AIVuln


def to_ai_service(svc: ScannedService) -> AIService:
    """转换为 AI 分析用的服务格式"""
    return AIService(
        host_ip=svc.host_ip,
        port=svc.port,
        protocol=svc.protocol,
        service_name=svc.service_name,
        product=svc.product,
        version=svc.version,
        banner=svc.banner,
    )


class PTScanner:
    """AI-PTS 扫描器封装"""

    def __init__(self, db_path: str = None):
        self.engine: ScanEngine = create_engine(db_path=db_path)
        self.last_result: Optional[ScanResult] = None

    def scan(
        self,
        target: str,
        ports: str = None,
        version_detect: bool = True,
        os_detect: bool = False,
        weak_pass: bool = False,
        zero_day_focus: bool = False,
        scan_type: str = "quick",
    ) -> ScanResult:
        """执行扫描"""
        self.last_result = self.engine.scan_sync(
            target=target,
            ports=ports,
            version_detect=version_detect,
            os_detect=os_detect,
            weak_pass=weak_pass,
            zero_day_focus=zero_day_focus,
            scan_type=scan_type,
        )
        return self.last_result

    def get_ai_services(self) -> List[AIService]:
        """获取 AI 分析用的服务列表"""
        if not self.last_result:
            return []
        return [to_ai_service(s) for s in self.last_result.services]

    def get_ai_vulnerabilities(self) -> List[AIVuln]:
        """获取 AI 分析用的漏洞列表"""
        if not self.last_result:
            return []
        return list(self.last_result.vulnerabilities)

    def search_vulns(
        self,
        product: str = None,
        severity: str = None,
        min_cvss: float = None,
        limit: int = 100,
    ) -> List[Dict]:
        """搜索漏洞"""
        return self.engine.search_vulns(
            product=product, severity=severity, min_cvss=min_cvss, limit=limit
        )

    def get_statistics(self) -> Dict:
        """获取漏洞库统计"""
        return self.engine.get_vuln_stats()


def create_scanner_instance(db_path: str = None) -> PTScanner:
    """创建扫描器实例"""
    return PTScanner(db_path=db_path)


def import_cve_data(json_path: str = None, db_path: str = None) -> int:
    """导入 CVE 数据（复用独立工具 import_cve.py 的 SQLite 导入）"""
    from import_cve import init_database, import_from_json

    init_database()
    return import_from_json(json_path) if json_path else 0


__all__ = [
    "PTScanner",
    "create_scanner_instance",
    "import_cve_data",
    "ScanEngine",
    "ScanResult",
    "ScannedHost",
    "ScannedService",
    "to_ai_service",
]
