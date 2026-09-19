"""
AI-PTS 自包含扫描器适配层

封装 vendored 的 ai-vuln 扫描引擎（vendor/ 目录，从 ai-vuln 复制而来），
对外提供 AI-PTS 原有代码所依赖的数据模型与接口，从而替代旧的
`vuln_scanner.core.engine` 幻影包，实现完全自包含、无兄弟项目引用。
"""
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# vendor 目录：自包含的 ai-vuln 扫描模块（scanner_engine / database / web_scanner 等）
VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

from core.ai_analyzer import Vulnerability  # noqa: E402


@dataclass
class ScannedHost:
    """扫描到的主机"""
    ip: str
    status: str = "up"
    hostname: str = ""
    mac: str = ""
    vendor: str = ""
    os: str = ""
    os_accuracy: str = ""


@dataclass
class ScannedService:
    """扫描到的服务"""
    host_ip: str
    port: int
    protocol: str = "tcp"
    service_name: str = ""
    product: str = ""
    version: str = ""
    banner: str = ""


@dataclass
class ScanResult:
    """扫描结果（对齐 main.py / gui 的既有用法）"""
    hosts: List[ScannedHost] = field(default_factory=list)
    services: List[ScannedService] = field(default_factory=list)
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    web_findings: List[Dict[str, Any]] = field(default_factory=list)
    scan_config: Dict[str, Any] = field(default_factory=dict)


def _to_vulnerability(v: Dict[str, Any]) -> Optional[Vulnerability]:
    """把 vendored 扫描引擎的漏洞 dict 转成 core.ai_analyzer.Vulnerability"""
    cve_id = v.get("cve_id")
    finding_type = v.get("finding_type")
    if not cve_id and not finding_type:
        return None
    if not cve_id:
        # 非 CVE 发现（弱口令/蜜罐/设备指纹），用 finding_type 作为标识，保留进结果
        cve_id = f"FINDING:{finding_type}"

    sev = str(v.get("severity") or "").strip().lower()
    sev_map = {
        "critical": "critical", "high": "high", "medium": "medium",
        "low": "low", "info": "low",
    }
    severity = sev_map.get(sev, "medium")

    try:
        cvss_score = float(v.get("cvss_score") or 0.0)
    except (TypeError, ValueError):
        cvss_score = 0.0

    return Vulnerability(
        cve_id=cve_id,
        description=(v.get("description") or ""),
        severity=severity,
        cvss_score=cvss_score,
        product=(v.get("product") or ""),
        version=(v.get("version") or ""),
        cwe_id=(v.get("cwe") or ""),
        exploit_available=bool(v.get("exploit_available")),
        host=(v.get("host") or ""),
        port=(v.get("port") or 0),
        service=(v.get("service") or ""),
        protocol=(v.get("protocol") or "tcp"),
        finding_type=(finding_type or ""),
        affected_versions=(v.get("affected_versions") or ""),
        references_url=(v.get("references_url") or ""),
        patch_link=(v.get("patch_link") or ""),
        match_confidence=(v.get("match_confidence") or ""),
        matched_by=(v.get("matched_by") or ""),
        evidence=(v.get("evidence") or {}),
        remediation=(v.get("remediation") or {}),
        raw=v,
    )


class ScanEngine:
    """封装 vendored VulnScanner + CVEDatabase 的扫描引擎"""

    def __init__(self, db_path: str = None, output_dir: str = None):
        # 延迟导入，确保 vendor 已在 sys.path 上
        from database import CVEDatabase
        from scanner_engine import VulnScanner as _VulnScanner

        self._db = CVEDatabase()
        self._scanner = _VulnScanner(db_manager=self._db)
        self.last_result: Optional[ScanResult] = None

    def scan_sync(
        self,
        target: str,
        ports: str = None,
        version_detect: bool = True,
        os_detect: bool = False,
        weak_pass: bool = False,
        zero_day_focus: bool = False,
        scan_type: str = "quick",
        web_scan: bool = False,
    ) -> ScanResult:
        """
        执行扫描，返回统一结构的 ScanResult。

        Args:
            target: 扫描目标（IP/CIDR/域名）
            ports: 端口范围（None 使用引擎默认端口）
            weak_pass: 是否做弱口令爆破（耗时）
            zero_day_focus: 是否做 0day 专项扫描
            web_scan: 是否做 Web 应用主动漏洞扫描
            scan_type: quick / full
        """
        raw = self._scanner.scan_target(
            target=target,
            ports=ports,
            scan_type=scan_type,
            weak_pass=weak_pass,
            zero_day_focus=zero_day_focus,
            version_detect=version_detect,
            os_detect=os_detect,
            web_scan=web_scan,
        )

        hosts: List[ScannedHost] = []
        services: List[ScannedService] = []

        scan_result = raw.get("scan_result") or {}
        for h in scan_result.get("hosts", []):
            ip = h.get("ip") or h.get("host", "")
            hosts.append(ScannedHost(
                ip=ip,
                status=h.get("status", "up"),
                hostname=h.get("hostname", ""),
                mac=h.get("mac", ""),
                vendor=h.get("vendor", ""),
                os=h.get("os", ""),
                os_accuracy=h.get("os_accuracy", ""),
            ))
            for p in h.get("ports", []):
                if p.get("state") not in (None, "", "open"):
                    continue
                product = p.get("product", "")
                version = p.get("version", "")
                services.append(ScannedService(
                    host_ip=ip,
                    port=p.get("port"),
                    protocol=p.get("protocol", "tcp"),
                    service_name=p.get("service", ""),
                    product=product,
                    version=version,
                    banner=f"{product} {version}".strip(),
                ))

        vulnerabilities = [
            vuln for vuln in (
                _to_vulnerability(v) for v in raw.get("vulnerabilities", [])
            )
            if vuln is not None
        ]

        web_findings = raw.get("web_scan_results") or []

        statistics = {
            "host_count": len(hosts),
            "service_count": len(services),
            "vuln_count": len(vulnerabilities),
            "zero_day_count": raw.get("zero_day_count", 0),
            "weak_password_count": raw.get("weak_password_count", 0),
            "honeypot_count": raw.get("honeypot_count", 0),
            "web_finding_count": len(web_findings),
            "duration": raw.get("duration", 0),
            "summary": raw.get("summary", {}),
        }

        scan_config = {
            "target": target,
            "ports": ports or "",
            "version_detect": version_detect,
            "os_detect": os_detect,
            "weak_pass": weak_pass,
            "zero_day_focus": zero_day_focus,
            "web_scan": web_scan,
            "scan_type": scan_type,
            "start_time": raw.get("start_time", ""),
            "end_time": raw.get("end_time", ""),
            "duration": raw.get("duration", 0),
        }

        result = ScanResult(
            hosts=hosts,
            services=services,
            vulnerabilities=vulnerabilities,
            statistics=statistics,
            web_findings=web_findings,
            scan_config=scan_config,
        )
        self.last_result = result
        return result

    # ---- 漏洞库相关（兼容 integrate.py / 其它调用）----

    def search_vulns(
        self,
        product: str = None,
        severity: str = None,
        min_cvss: float = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        # 需要后置过滤时先取全量，避免"先 limit 后 filter"导致结果不足 limit
        need_post_filter = bool(severity) or (product is not None and min_cvss is not None)
        fetch_limit = 9990000 if need_post_filter else limit

        if product:
            rows = self._db.search_cve_by_product(product, limit=fetch_limit)
        else:
            rows = self._db.search_cve(keyword=None, min_cvss=min_cvss or 0, limit=fetch_limit)

        if severity:
            rows = [r for r in rows if str(r.get("severity", "")).lower() == severity.lower()]
        if min_cvss is not None:
            rows = [r for r in rows if (r.get("cvss_score") or 0) >= min_cvss]
        return rows[:limit]

    def get_vuln_stats(self) -> Dict[str, Any]:
        return self._db.get_statistics()


def create_engine(db_path: str = None, output_dir: str = None) -> ScanEngine:
    """创建扫描引擎实例（兼容旧 create_engine 调用）"""
    return ScanEngine(db_path=db_path, output_dir=output_dir)


def create_scanner(db_path: str = None, output_dir: str = None) -> ScanEngine:
    """别名：创建扫描器实例"""
    return create_engine(db_path, output_dir)


__all__ = [
    "ScanEngine",
    "ScanResult",
    "ScannedHost",
    "ScannedService",
    "create_engine",
    "create_scanner",
]
