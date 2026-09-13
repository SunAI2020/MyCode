"""
核心扫描引擎
整合扫描器、匹配器和报告生成器
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from database import VulnerabilityDatabase, ScanResult, ScannedHost, ScannedService, FoundVulnerability
from scanner import create_scanner, create_matcher
from report import ReportGenerator
from config.settings import SCAN, REPORT

logger = logging.getLogger(__name__)


class ScanEngine:
    """漏洞扫描引擎"""
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        output_dir: Optional[str] = None
    ):
        """
        初始化扫描引擎
        
        Args:
            db_path: 漏洞数据库路径
            output_dir: 报告输出目录
        """
        self.vuln_db = VulnerabilityDatabase(db_path)
        self.scanner = create_scanner()
        self.matcher = create_matcher(self.vuln_db)
        self.report_gen = ReportGenerator(output_dir)
        
        self._current_scan_id: Optional[str] = None
        self._scan_running = False
        self._scan_paused = False
    
    def initialize_database(self, cve_data_path: Optional[str] = None):
        """
        初始化漏洞数据库
        
        Args:
            cve_data_path: CVE 示例数据路径
        """
        stats = self.vuln_db.get_statistics()
        
        if stats['total_cves'] == 0 and cve_data_path:
            logger.info(f"从 {cve_data_path} 加载 CVE 数据...")
            count = self.vuln_db.load_from_json(cve_data_path)
            logger.info(f"成功加载 {count} 条 CVE 记录")
        else:
            logger.info(f"数据库已有 {stats['total_cves']} 条 CVE 记录")
        
        return stats
    
    async def scan(
        self,
        target: str,
        ports: Optional[str] = None,
        version_detect: bool = True,
        os_detect: bool = False,
        generate_report: bool = True,
        report_formats: Optional[List[str]] = None
    ) -> ScanResult:
        """
        执行漏洞扫描
        
        Args:
            target: 扫描目标（IP、范围、文件或 CIDR）
            ports: 端口范围
            version_detect: 是否进行版本检测
            os_detect: 是否进行操作系统检测
            generate_report: 是否生成报告
            report_formats: 报告格式列表
            
        Returns:
            ScanResult: 扫描结果
        """
        self._current_scan_id = str(uuid.uuid4())[:8]
        self._scan_running = True
        start_time = datetime.now().isoformat()
        
        logger.info(f"开始扫描任务：{self._current_scan_id}")
        logger.info(f"扫描目标：{target}")
        
        try:
            # 解析目标
            logger.info("解析扫描目标...")
            hosts = self.scanner.parse_targets(target)
            logger.info(f"解析到 {len(hosts)} 个主机")
            
            if not hosts:
                raise ValueError("未找到有效的扫描目标")
            
            # 执行扫描
            logger.info("执行端口扫描和服务识别...")
            scan_results = await self.scanner.scan_hosts_async(
                hosts=hosts,
                ports=ports,
                max_concurrent=SCAN['max_concurrent_hosts']
            )
            
            # 整理扫描结果
            all_hosts: List[ScannedHost] = []
            all_services: List[ScannedService] = []
            
            for host, services in scan_results:
                if host:
                    all_hosts.append(host)
                    all_services.extend(services)
            
            logger.info(f"扫描完成：{len(all_hosts)} 台主机，{len(all_services)} 个服务")
            
            # 漏洞匹配
            logger.info("执行漏洞匹配...")
            vulnerabilities = self.matcher.match_all_services(all_services)
            logger.info(f"发现 {len(vulnerabilities)} 个漏洞")
            
            # 生成统计
            end_time = datetime.now().isoformat()
            statistics = self.matcher.get_statistics(vulnerabilities)
            
            # 创建扫描结果
            result = ScanResult(
                scan_id=self._current_scan_id,
                target=target,
                start_time=start_time,
                end_time=end_time,
                hosts=all_hosts,
                services=all_services,
                vulnerabilities=vulnerabilities,
                statistics=statistics
            )
            
            # 生成报告
            if generate_report and vulnerabilities:
                logger.info("生成扫描报告...")
                formats = report_formats or REPORT['formats']
                report_paths = self.report_gen.generate_reports(result, formats)
                result.statistics['report_paths'] = report_paths
            
            logger.info(f"扫描任务完成：{self._current_scan_id}")
            return result
            
        except Exception as e:
            logger.error(f"扫描失败：{e}", exc_info=True)
            raise
        finally:
            self._scan_running = False
            self._current_scan_id = None
    
    def scan_sync(
        self,
        target: str,
        ports: Optional[str] = None,
        version_detect: bool = True,
        os_detect: bool = False,
        generate_report: bool = True,
        report_formats: Optional[List[str]] = None
    ) -> ScanResult:
        """
        同步执行扫描（ convenience 方法）
        
        Args:
            target: 扫描目标
            ports: 端口范围
            version_detect: 是否进行版本检测
            os_detect: 是否进行操作系统检测
            generate_report: 是否生成报告
            report_formats: 报告格式列表
            
        Returns:
            ScanResult: 扫描结果
        """
        # Python 3.6 兼容：使用 get_event_loop 而不是 asyncio.run
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.scan(
            target=target,
            ports=ports,
            version_detect=version_detect,
            os_detect=os_detect,
            generate_report=generate_report,
            report_formats=report_formats
        ))
    
    def pause_scan(self):
        """暂停扫描"""
        self._scan_paused = True
        self.scanner.pause()
        logger.info("扫描已暂停")
    
    def resume_scan(self):
        """恢复扫描"""
        self._scan_paused = False
        self.scanner.resume()
        logger.info("扫描已恢复")
    
    def cancel_scan(self):
        """取消扫描"""
        self.scanner.cancel()
        self._scan_running = False
        logger.info("扫描已取消")
    
    def get_vuln_stats(self) -> Dict[str, Any]:
        """获取漏洞库统计"""
        return self.vuln_db.get_statistics()
    
    def search_vulnerabilities(
        self,
        product: Optional[str] = None,
        severity: Optional[str] = None,
        min_cvss: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        搜索漏洞
        
        Args:
            product: 产品名称
            severity: 严重程度
            min_cvss: 最小 CVSS 分数
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 漏洞列表
        """
        from database import Severity
        
        severity_enum = None
        if severity:
            try:
                severity_enum = Severity[severity.upper()]
            except KeyError:
                pass
        
        cves = self.vuln_db.search_vulnerabilities(
            product=product,
            severity=severity_enum,
            min_cvss=min_cvss,
            limit=limit
        )
        
        return [cve.to_dict() for cve in cves]
    
    def export_vuln_db(self, output_path: str, limit: Optional[int] = None) -> int:
        """
        导出漏洞数据库
        
        Args:
            output_path: 输出文件路径
            limit: 导出数量限制
            
        Returns:
            int: 导出数量
        """
        return self.vuln_db.export_to_json(output_path, limit)


def create_engine(
    db_path: Optional[str] = None,
    output_dir: Optional[str] = None
) -> ScanEngine:
    """创建扫描引擎实例"""
    return ScanEngine(db_path=db_path, output_dir=output_dir)
