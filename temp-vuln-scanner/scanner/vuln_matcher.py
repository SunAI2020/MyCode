"""
漏洞匹配引擎
根据扫描结果匹配漏洞库中的漏洞
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from database.models import CVE, ScannedService, FoundVulnerability, Severity
from database.vuln_database import VulnerabilityDatabase
from config.settings import CVSS_THRESHOLDS

logger = logging.getLogger(__name__)


@dataclass
class MatchConfidence:
    """匹配置信度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VersionMatcher:
    """版本匹配器"""
    
    @staticmethod
    def parse_version(version_str: str) -> Tuple[int, ...]:
        """
        解析版本号
        
        Args:
            version_str: 版本字符串，如 "1.2.3"
            
        Returns:
            Tuple[int, ...]: 版本号元组
        """
        if not version_str:
            return (0,)
        
        # 提取数字部分
        numbers = re.findall(r'\d+', version_str)
        if not numbers:
            return (0,)
        
        return tuple(int(n) for n in numbers)
    
    @staticmethod
    def version_in_range(
        version: str,
        affected_versions: List[str]
    ) -> bool:
        """
        检查版本是否在受影响版本范围内
        
        Args:
            version: 当前版本
            affected_versions: 受影响版本列表
            
        Returns:
            bool: 是否受影响
        """
        if not version or not affected_versions:
            return False
        
        current = VersionMatcher.parse_version(version)
        
        for affected in affected_versions:
            affected_tuple = VersionMatcher.parse_version(affected)
            
            # 精确匹配
            if current == affected_tuple:
                return True
            
            # 主版本匹配（如果受影响版本只有一位）
            if len(affected_tuple) == 1 and current[0] == affected_tuple[0]:
                return True
            
            # 主版本和次版本匹配
            if len(affected_tuple) >= 2 and len(current) >= 2:
                if current[0] == affected_tuple[0] and current[1] == affected_tuple[1]:
                    return True
        
        return False
    
    @staticmethod
    def product_match(
        scanned_product: str,
        cve_products: List[str]
    ) -> Optional[str]:
        """
        匹配产品名称
        
        Args:
            scanned_product: 扫描到的产品名称
            cve_products: CVE 中的产品列表
            
        Returns:
            Optional[str]: 匹配的产品名称
        """
        if not scanned_product or not cve_products:
            return None
        
        scanned_lower = scanned_product.lower().strip()
        
        for cve_product in cve_products:
            cve_lower = cve_product.lower().strip()
            
            # 精确匹配
            if scanned_lower == cve_lower:
                return cve_product
            
            # 包含匹配
            if cve_lower in scanned_lower or scanned_lower in cve_lower:
                return cve_product
            
            # 别名匹配（常见产品别名）
            aliases = VersionMatcher._get_product_aliases(cve_lower)
            for alias in aliases:
                if alias in scanned_lower:
                    return cve_product
        
        return None
    
    @staticmethod
    def _get_product_aliases(product: str) -> List[str]:
        """获取产品别名"""
        aliases_map = {
            'apache': ['httpd', 'web server'],
            'nginx': ['web server'],
            'openssh': ['ssh', 'ssh server'],
            'openssl': ['ssl', 'tls'],
            'mysql': ['mariadb', 'database'],
            'postgresql': ['postgres', 'database'],
            'microsoft windows': ['windows', 'win'],
            'apache tomcat': ['tomcat'],
            'oracle weblogic': ['weblogic'],
            'jenkins': ['ci/cd'],
            'docker': ['container'],
            'kubernetes': ['k8s'],
        }
        return aliases_map.get(product, [])


class VulnerabilityMatcher:
    """漏洞匹配引擎"""
    
    def __init__(self, vuln_db: VulnerabilityDatabase):
        """
        初始化匹配引擎
        
        Args:
            vuln_db: 漏洞数据库实例
        """
        self.vuln_db = vuln_db
        self.version_matcher = VersionMatcher()
        self._false_positive_cache = set()  # 误报缓存
    
    def match_service(
        self,
        service: ScannedService
    ) -> List[FoundVulnerability]:
        """
        匹配单个服务的漏洞
        
        Args:
            service: 扫描服务信息
            
        Returns:
            List[FoundVulnerability]: 发现的漏洞列表
        """
        vulnerabilities = []
        
        # 检查是否在误报缓存中
        cache_key = f"{service.host_ip}:{service.port}:{service.product}:{service.version}"
        if cache_key in self._false_positive_cache:
            return []
        
        # 根据产品名称搜索漏洞
        if service.product:
            cves = self.vuln_db.match_vulnerability(
                product=service.product,
                version=service.version
            )
            
            for cve in cves:
                # 检查产品匹配
                matched_product = self.version_matcher.product_match(
                    service.product,
                    cve.affected_products
                )
                
                if not matched_product:
                    continue
                
                # 检查版本匹配
                version_matched = self.version_matcher.version_in_range(
                    service.version,
                    cve.affected_versions
                )
                
                if version_matched:
                    # 确定置信度
                    confidence = self._calculate_confidence(
                        service, cve, matched_product
                    )
                    
                    vuln = FoundVulnerability(
                        cve=cve,
                        host_ip=service.host_ip,
                        port=service.port,
                        service=service.service_name,
                        matched_version=service.version,
                        confidence=confidence
                    )
                    vulnerabilities.append(vuln)
        
        # 根据服务名称搜索（当产品名为空时）
        if not service.product and service.service_name:
            cves = self.vuln_db.search_vulnerabilities(
                product=service.service_name,
                limit=100
            )
            
            for cve in cves:
                matched_product = self.version_matcher.product_match(
                    service.service_name,
                    cve.affected_products
                )
                
                if matched_product:
                    vuln = FoundVulnerability(
                        cve=cve,
                        host_ip=service.host_ip,
                        port=service.port,
                        service=service.service_name,
                        matched_version=service.version or "unknown",
                        confidence=MatchConfidence.LOW
                    )
                    vulnerabilities.append(vuln)
        
        logger.debug(f"服务 {service.host_ip}:{service.port} 匹配到 {len(vulnerabilities)} 个漏洞")
        return vulnerabilities
    
    def _calculate_confidence(
        self,
        service: ScannedService,
        cve: CVE,
        matched_product: str
    ) -> str:
        """
        计算匹配置信度
        
        Args:
            service: 扫描服务
            cve: CVE 信息
            matched_product: 匹配的产品
            
        Returns:
            str: 置信度 (high/medium/low)
        """
        score = 0
        
        # 产品精确匹配
        if service.product.lower() == matched_product.lower():
            score += 3
        else:
            score += 1
        
        # 版本匹配
        if service.version and self.version_matcher.version_in_range(
            service.version, cve.affected_versions
        ):
            score += 3
        elif service.version:
            score += 1
        
        # 端口匹配（常见服务端口）
        common_ports = {
            22: ['ssh', 'openssh'],
            80: ['http', 'apache', 'nginx'],
            443: ['https', 'apache', 'nginx'],
            3306: ['mysql', 'mariadb'],
            5432: ['postgresql', 'postgres'],
            8080: ['http', 'tomcat', 'jenkins'],
        }
        
        if service.port in common_ports:
            for svc in common_ports[service.port]:
                if svc in service.service_name.lower() or svc in service.product.lower():
                    score += 2
                    break
        
        # Banner 信息匹配
        if service.banner and cve.name.lower() in service.banner.lower():
            score += 2
        
        # 确定置信度
        if score >= 6:
            return MatchConfidence.HIGH
        elif score >= 3:
            return MatchConfidence.MEDIUM
        else:
            return MatchConfidence.LOW
    
    def mark_false_positive(self, vuln: FoundVulnerability):
        """
        标记为误报
        
        Args:
            vuln: 漏洞实例
        """
        cache_key = f"{vuln.host_ip}:{vuln.port}:{vuln.cve.cve_id}"
        self._false_positive_cache.add(cache_key)
        logger.info(f"标记误报：{cache_key}")
    
    def match_all_services(
        self,
        services: List[ScannedService]
    ) -> List[FoundVulnerability]:
        """
        匹配所有服务的漏洞
        
        Args:
            services: 服务列表
            
        Returns:
            List[FoundVulnerability]: 所有发现的漏洞
        """
        all_vulnerabilities = []
        
        for service in services:
            vulns = self.match_service(service)
            all_vulnerabilities.extend(vulns)
        
        # 按严重程度排序
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }
        
        all_vulnerabilities.sort(
            key=lambda v: (severity_order.get(v.cve.severity, 5), -v.cve.cvss_score)
        )
        
        return all_vulnerabilities
    
    def get_statistics(
        self,
        vulnerabilities: List[FoundVulnerability]
    ) -> Dict:
        """
        获取漏洞统计信息
        
        Args:
            vulnerabilities: 漏洞列表
            
        Returns:
            Dict: 统计信息
        """
        stats = {
            'total': len(vulnerabilities),
            'by_severity': {},
            'by_confidence': {},
            'by_host': {},
            'critical_count': 0,
            'high_count': 0,
            'exploitable_count': 0,
        }
        
        for vuln in vulnerabilities:
            # 按严重程度统计
            severity = vuln.cve.severity.value
            stats['by_severity'][severity] = stats['by_severity'].get(severity, 0) + 1
            
            # 按置信度统计
            confidence = vuln.confidence
            stats['by_confidence'][confidence] = stats['by_confidence'].get(confidence, 0) + 1
            
            # 按主机统计
            host = vuln.host_ip
            stats['by_host'][host] = stats['by_host'].get(host, 0) + 1
            
            # 统计关键漏洞
            if vuln.cve.severity == Severity.CRITICAL:
                stats['critical_count'] += 1
            elif vuln.cve.severity == Severity.HIGH:
                stats['high_count'] += 1
            
            # 统计可利用漏洞
            if vuln.cve.exploit_available:
                stats['exploitable_count'] += 1
        
        return stats


def create_matcher(vuln_db: VulnerabilityDatabase) -> VulnerabilityMatcher:
    """创建匹配引擎实例"""
    return VulnerabilityMatcher(vuln_db)
