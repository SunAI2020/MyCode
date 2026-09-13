"""
漏洞数据模型定义
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class Severity(Enum):
    """漏洞严重程度"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class CVE:
    """CVE 漏洞数据结构"""
    cve_id: str  # CVE 编号，如 CVE-2021-44228
    name: str  # 漏洞名称
    description: str  # 漏洞描述
    affected_products: List[str]  # 受影响的产品列表
    affected_versions: List[str]  # 受影响的版本
    cvss_score: float  # CVSS 评分 (0.0-10.0)
    severity: Severity  # 严重程度
    published_date: str  # 发布日期
    modified_date: str  # 修改日期
    references: List[str]  # 参考链接
    fix_recommendation: str  # 修复建议
    cwe_id: Optional[str] = None  # CWE 编号
    exploit_available: bool = False  # 是否有公开利用代码
    patch_available: bool = True  # 是否有补丁
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'cve_id': self.cve_id,
            'name': self.name,
            'description': self.description,
            'affected_products': self.affected_products,
            'affected_versions': self.affected_versions,
            'cvss_score': self.cvss_score,
            'severity': self.severity.value,
            'published_date': self.published_date,
            'modified_date': self.modified_date,
            'references': self.references,
            'fix_recommendation': self.fix_recommendation,
            'cwe_id': self.cwe_id,
            'exploit_available': self.exploit_available,
            'patch_available': self.patch_available,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CVE':
        """从字典创建"""
        return cls(
            cve_id=data['cve_id'],
            name=data['name'],
            description=data['description'],
            affected_products=data.get('affected_products', []),
            affected_versions=data.get('affected_versions', []),
            cvss_score=data.get('cvss_score', 0.0),
            severity=Severity(data.get('severity', 'MEDIUM')),
            published_date=data.get('published_date', ''),
            modified_date=data.get('modified_date', ''),
            references=data.get('references', []),
            fix_recommendation=data.get('fix_recommendation', ''),
            cwe_id=data.get('cwe_id'),
            exploit_available=data.get('exploit_available', False),
            patch_available=data.get('patch_available', True),
        )


@dataclass
class ScannedHost:
    """扫描主机信息"""
    ip: str
    hostname: Optional[str] = None
    os: Optional[str] = None
    os_version: Optional[str] = None
    mac_address: Optional[str] = None
    status: str = "up"  # up/down
    scanned_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ScannedService:
    """扫描服务信息"""
    host_ip: str
    port: int
    protocol: str  # tcp/udp
    service_name: str  # 服务名称，如 http, ssh
    product: str  # 产品名称，如 Apache, OpenSSH
    version: str  # 版本号
    extra_info: Optional[str] = None
    banner: Optional[str] = None


@dataclass
class FoundVulnerability:
    """发现的漏洞"""
    cve: CVE
    host_ip: str
    port: int
    service: str
    matched_version: str
    confidence: str  # high/medium/low
    found_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'cve': self.cve.to_dict(),
            'host_ip': self.host_ip,
            'port': self.port,
            'service': self.service,
            'matched_version': self.matched_version,
            'confidence': self.confidence,
            'found_at': self.found_at,
        }


@dataclass
class ScanResult:
    """扫描结果"""
    scan_id: str
    target: str  # 扫描目标
    start_time: str
    end_time: str
    hosts: List[ScannedHost] = field(default_factory=list)
    services: List[ScannedService] = field(default_factory=list)
    vulnerabilities: List[FoundVulnerability] = field(default_factory=list)
    statistics: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'scan_id': self.scan_id,
            'target': self.target,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'hosts': [h.__dict__ for h in self.hosts],
            'services': [s.__dict__ for s in self.services],
            'vulnerabilities': [v.to_dict() for v in self.vulnerabilities],
            'statistics': self.statistics,
        }
