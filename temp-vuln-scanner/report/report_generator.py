"""
报告生成模块
生成 HTML、JSON、PDF 格式的扫描报告
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape

from database import ScanResult, FoundVulnerability, Severity
from config.settings import REPORT

logger = logging.getLogger(__name__)


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, output_dir: Optional[str] = None):
        """
        初始化报告生成器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir) if output_dir else REPORT['output_dir']
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化 Jinja2 环境
        template_dir = Path(REPORT['template_dir'])
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # 注册自定义过滤器
        self.jinja_env.filters['cvss_color'] = self._cvss_color
        self.jinja_env.filters['severity_color'] = self._severity_color
        self.jinja_env.filters['format_datetime'] = self._format_datetime
    
    def _cvss_color(self, score: float) -> str:
        """根据 CVSS 分数返回颜色"""
        if score >= 9.0:
            return '#dc3545'  # 红色
        elif score >= 7.0:
            return '#fd7e14'  # 橙色
        elif score >= 4.0:
            return '#ffc107'  # 黄色
        elif score > 0:
            return '#28a745'  # 绿色
        else:
            return '#6c757d'  # 灰色
    
    def _severity_color(self, severity: str) -> str:
        """根据严重程度返回颜色"""
        colors = {
            'CRITICAL': '#dc3545',
            'HIGH': '#fd7e14',
            'MEDIUM': '#ffc107',
            'LOW': '#28a745',
            'INFO': '#6c757d',
        }
        return colors.get(severity, '#6c757d')
    
    def _format_datetime(self, dt_str: str) -> str:
        """格式化日期时间"""
        try:
            dt = datetime.fromisoformat(dt_str)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return dt_str
    
    def generate_reports(
        self,
        result: ScanResult,
        formats: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        生成多种格式的报告
        
        Args:
            result: 扫描结果
            formats: 报告格式列表
            
        Returns:
            Dict[str, str]: 生成的报告文件路径
        """
        formats = formats or REPORT['formats']
        generated = {}
        
        for fmt in formats:
            try:
                if fmt == 'html':
                    path = self.generate_html_report(result)
                    generated['html'] = str(path)
                elif fmt == 'json':
                    path = self.generate_json_report(result)
                    generated['json'] = str(path)
                elif fmt == 'pdf':
                    path = self.generate_pdf_report(result)
                    generated['pdf'] = str(path)
            except Exception as e:
                logger.error(f"生成 {fmt} 报告失败：{e}")
        
        return generated
    
    def generate_html_report(self, result: ScanResult) -> Path:
        """
        生成 HTML 报告
        
        Args:
            result: 扫描结果
            
        Returns:
            Path: 报告文件路径
        """
        template = self.jinja_env.get_template('report.html')
        
        # 准备报告数据
        report_data = self._prepare_report_data(result)
        
        # 渲染模板
        html_content = template.render(**report_data)
        
        # 保存文件
        filename = f"vuln_scan_{result.scan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML 报告已生成：{output_path}")
        return output_path
    
    def generate_json_report(self, result: ScanResult) -> Path:
        """
        生成 JSON 报告
        
        Args:
            result: 扫描结果
            
        Returns:
            Path: 报告文件路径
        """
        report_data = self._prepare_report_data(result)
        
        filename = f"vuln_scan_{result.scan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"JSON 报告已生成：{output_path}")
        return output_path
    
    def generate_pdf_report(self, result: ScanResult) -> Path:
        """
        生成 PDF 报告（通过 HTML 转换）
        
        Args:
            result: 扫描结果
            
        Returns:
            Path: 报告文件路径
        """
        # 先生成 HTML
        html_path = self.generate_html_report(result)
        
        # 尝试转换为 PDF
        try:
            import pdfkit
            
            filename = f"vuln_scan_{result.scan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            output_path = self.output_dir / filename
            
            pdfkit.from_file(str(html_path), str(output_path))
            logger.info(f"PDF 报告已生成：{output_path}")
            return output_path
            
        except ImportError:
            logger.warning("pdfkit 未安装，跳过 PDF 报告生成")
            return html_path
        except Exception as e:
            logger.warning(f"PDF 转换失败：{e}，返回 HTML 报告")
            return html_path
    
    def _prepare_report_data(self, result: ScanResult) -> Dict[str, Any]:
        """
        准备报告数据
        
        Args:
            result: 扫描结果
            
        Returns:
            Dict: 报告数据
        """
        # 按严重程度分组漏洞
        vulns_by_severity = {}
        for vuln in result.vulnerabilities:
            severity = vuln.cve.severity.value
            if severity not in vulns_by_severity:
                vulns_by_severity[severity] = []
            vulns_by_severity[severity].append(vuln)
        
        # 按主机分组漏洞
        vulns_by_host = {}
        for vuln in result.vulnerabilities:
            host = vuln.host_ip
            if host not in vulns_by_host:
                vulns_by_host[host] = []
            vulns_by_host[host].append(vuln)
        
        return {
            'scan_id': result.scan_id,
            'target': result.target,
            'start_time': result.start_time,
            'end_time': result.end_time,
            'hosts': result.hosts,
            'services': result.services,
            'vulnerabilities': result.vulnerabilities,
            'vulns_by_severity': vulns_by_severity,
            'vulns_by_host': vulns_by_host,
            'statistics': result.statistics,
            'total_vulns': len(result.vulnerabilities),
            'total_hosts': len(result.hosts),
            'total_services': len(result.services),
            'generated_at': datetime.now().isoformat(),
        }
    
    def generate_executive_summary(self, result: ScanResult) -> str:
        """
        生成执行摘要
        
        Args:
            result: 扫描结果
            
        Returns:
            str: 执行摘要文本
        """
        stats = result.statistics
        
        summary = []
        summary.append("=" * 60)
        summary.append("漏洞扫描执行摘要")
        summary.append("=" * 60)
        summary.append(f"扫描 ID: {result.scan_id}")
        summary.append(f"扫描目标：{result.target}")
        summary.append(f"扫描时间：{result.start_time} - {result.end_time}")
        summary.append("")
        summary.append("【统计信息】")
        summary.append(f"  - 扫描主机：{stats.get('total_hosts', len(result.hosts))}")
        summary.append(f"  - 发现服务：{len(result.services)}")
        summary.append(f"  - 发现漏洞：{stats.get('total', len(result.vulnerabilities))}")
        summary.append("")
        summary.append("【按严重程度分类】")
        
        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']:
            count = stats.get('by_severity', {}).get(severity, 0)
            if count > 0:
                summary.append(f"  - {severity}: {count}")
        
        summary.append("")
        
        if stats.get('critical_count', 0) > 0:
            summary.append("⚠️  警告：发现严重漏洞，需要立即处理！")
        
        if stats.get('exploitable_count', 0) > 0:
            summary.append(f"⚠️  注意：{stats['exploitable_count']} 个漏洞存在公开利用代码")
        
        summary.append("")
        summary.append("=" * 60)
        
        return "\n".join(summary)


def create_report_generator(output_dir: Optional[str] = None) -> ReportGenerator:
    """创建报告生成器实例"""
    return ReportGenerator(output_dir=output_dir)
