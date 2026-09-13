#!/usr/bin/env python3
"""
漏洞扫描系统 - 命令行接口
"""
import sys
import asyncio
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import box

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from core import create_engine
from database import VulnerabilityDatabase
from utils import (
    setup_logging,
    print_banner,
    print_disclaimer,
    confirm_license,
    format_cvss,
    format_severity,
)
from config.settings import DATABASE, LEGAL

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version='1.0.0', prog_name='vuln-scanner')
@click.pass_context
def cli(ctx):
    """🔒 漏洞扫描系统 - 授权安全测试工具"""
    ctx.ensure_object(dict)
    print_banner()


@cli.command()
@click.option('--target', '-t', required=True, help='扫描目标 (IP/IP 范围/CIDR/文件)')
@click.option('--ports', '-p', default=None, help='端口范围 (如：1-1000,8080,443)')
@click.option('--output', '-o', default=None, help='报告输出目录')
@click.option('--format', '-f', 'report_formats', multiple=True, 
              type=click.Choice(['html', 'json', 'pdf']), default=['html'],
              help='报告格式')
@click.option('--no-report', is_flag=True, help='不生成报告')
@click.option('--skip-license', is_flag=True, help='跳过许可确认')
@click.pass_context
def scan(ctx, target, ports, output, report_formats, no_report, skip_license):
    """执行漏洞扫描"""
    
    # 许可确认
    if not skip_license and LEGAL['license_required']:
        if not confirm_license():
            console.print("[red]✗ 已取消操作[/red]")
            return
    
    # 设置日志
    setup_logging(level='INFO')
    
    try:
        # 创建引擎
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            
            task = progress.add_task("初始化扫描引擎...", total=None)
            engine = create_engine(output_dir=output)
            
            # 初始化数据库
            progress.update(task, description="加载漏洞数据库...")
            stats = engine.initialize_database(DATABASE['cve_data_path'])
            
            console.print(Panel(
                f"[green]✓[/green] 漏洞库已加载\n"
                f"  总 CVE 数：[bold]{stats['total_cves']}[/bold]\n"
                f"  严重：{stats['by_severity'].get('CRITICAL', 0)} | "
                f"高危：{stats['by_severity'].get('HIGH', 0)} | "
                f"中危：{stats['by_severity'].get('MEDIUM', 0)}",
                title="📊 数据库状态",
                box=box.ROUNDED
            ))
            
            # 执行扫描
            progress.update(task, description=f"扫描目标：{target}")
            
            # Python 3.6 兼容：使用 get_event_loop 而不是 asyncio.run
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(engine.scan(
                target=target,
                ports=ports,
                version_detect=True,
                os_detect=False,
                generate_report=not no_report,
                report_formats=list(report_formats) if report_formats else ['html']
            ))
        
        # 显示结果摘要
        console.print("\n[bold green]✓ 扫描完成![/bold green]\n")
        
        # 统计表格
        stats_table = Table(title="📈 扫描统计", box=box.ROUNDED)
        stats_table.add_column("指标", style="cyan")
        stats_table.add_column("数值", style="green")
        
        stats_table.add_row("扫描目标", result.target)
        stats_table.add_row("扫描主机", str(len(result.hosts)))
        stats_table.add_row("发现服务", str(len(result.services)))
        stats_table.add_row("发现漏洞", str(len(result.vulnerabilities)))
        
        if result.statistics:
            stats_table.add_row("严重漏洞", str(result.statistics.get('critical_count', 0)), style="red")
            stats_table.add_row("高危漏洞", str(result.statistics.get('high_count', 0)), style="magenta")
            stats_table.add_row("可利用漏洞", str(result.statistics.get('exploitable_count', 0)), style="yellow")
        
        console.print(stats_table)
        
        # 显示漏洞列表
        if result.vulnerabilities:
            vuln_table = Table(title="🔍 发现的漏洞", box=box.ROUNDED)
            vuln_table.add_column("CVE 编号", style="cyan")
            vuln_table.add_column("名称", style="white")
            vuln_table.add_column("主机", style="green")
            vuln_table.add_column("CVSS", justify="center")
            vuln_table.add_column("严重程度", justify="center")
            
            for vuln in result.vulnerabilities[:20]:  # 只显示前 20 个
                vuln_table.add_row(
                    vuln.cve.cve_id,
                    vuln.cve.name[:40] + "..." if len(vuln.cve.name) > 40 else vuln.cve.name,
                    f"{vuln.host_ip}:{vuln.port}",
                    f"{vuln.cve.cvss_score:.1f}",
                    vuln.cve.severity.value
                )
            
            console.print(vuln_table)
            
            if len(result.vulnerabilities) > 20:
                console.print(f"[yellow]... 还有 {len(result.vulnerabilities) - 20} 个漏洞，请查看报告[/yellow]")
        
        # 显示报告路径
        if not no_report and result.statistics.get('report_paths'):
            console.print("\n[bold]📁 报告文件:[/bold]")
            for fmt, path in result.statistics['report_paths'].items():
                console.print(f"  {fmt.upper()}: [cyan]{path}[/cyan]")
        
    except Exception as e:
        console.print(f"[red]✗ 扫描失败：{e}[/red]")
        logger.exception("扫描失败")
        sys.exit(1)


@cli.command()
@click.option('--product', '-p', default=None, help='产品名称')
@click.option('--severity', '-s', type=click.Choice(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']),
              help='严重程度')
@click.option('--min-cvss', type=float, help='最小 CVSS 分数')
@click.option('--limit', '-l', default=20, help='返回数量限制')
@click.option('--db-path', default=None, help='数据库路径')
def search(product, severity, min_cvss, limit, db_path):
    """搜索漏洞库"""
    
    setup_logging(level='WARNING')
    
    try:
        db = VulnerabilityDatabase(db_path)
        cves = db.search_vulnerabilities(
            product=product,
            severity=None,  # 暂时不转换，由数据库处理
            min_cvss=min_cvss,
            limit=limit
        )
        
        if not cves:
            console.print("[yellow]未找到匹配的漏洞[/yellow]")
            return
        
        table = Table(title=f"📚 漏洞库搜索 (找到 {len(cves)} 条)", box=box.ROUNDED)
        table.add_column("CVE 编号", style="cyan")
        table.add_column("名称", style="white")
        table.add_column("CVSS", justify="center")
        table.add_column("严重程度", justify="center")
        table.add_column("发布日期")
        
        for cve in cves:
            table.add_row(
                cve.cve_id,
                cve.name[:50] + "..." if len(cve.name) > 50 else cve.name,
                f"{cve.cvss_score:.1f}",
                cve.severity.value,
                cve.published_date[:10] if cve.published_date else "-"
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]✗ 搜索失败：{e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--db-path', default=None, help='数据库路径')
def stats(db_path):
    """显示漏洞库统计信息"""
    
    setup_logging(level='WARNING')
    
    try:
        db = VulnerabilityDatabase(db_path)
        stats = db.get_statistics()
        
        console.print(Panel(
            f"[bold]总 CVE 数:[/bold] {stats['total_cves']}\n\n"
            f"[bold]按严重程度:[/bold]\n"
            f"  CRITICAL: {stats['by_severity'].get('CRITICAL', 0)}\n"
            f"  HIGH: {stats['by_severity'].get('HIGH', 0)}\n"
            f"  MEDIUM: {stats['by_severity'].get('MEDIUM', 0)}\n"
            f"  LOW: {stats['by_severity'].get('LOW', 0)}\n"
            f"  INFO: {stats['by_severity'].get('INFO', 0)}\n\n"
            f"[bold]有利用代码的漏洞:[/bold] {stats.get('with_exploit', 0)}",
            title="📊 漏洞库统计",
            box=box.ROUNDED
        ))
        
        if stats.get('by_year'):
            table = Table(title="📅 按年份分布", box=box.ROUNDED)
            table.add_column("年份", style="cyan")
            table.add_column("CVE 数量", style="green")
            
            for year, count in list(stats['by_year'].items())[:10]:
                table.add_row(year, str(count))
            
            console.print(table)
        
    except Exception as e:
        console.print(f"[red]✗ 获取统计失败：{e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--cve-id', '-c', required=True, help='CVE 编号')
@click.option('--db-path', default=None, help='数据库路径')
def detail(cve_id, db_path):
    """查看 CVE 详情"""
    
    setup_logging(level='WARNING')
    
    try:
        db = VulnerabilityDatabase(db_path)
        cve = db.get_cve(cve_id)
        
        if not cve:
            console.print(f"[red]✗ 未找到 CVE: {cve_id}[/red]")
            return
        
        console.print(Panel(
            f"[bold cyan]{cve.cve_id}[/bold cyan]\n\n"
            f"[bold]名称:[/bold] {cve.name}\n"
            f"[bold]CVSS 分数:[/bold] {cve.cvss_score:.1f}\n"
            f"[bold]严重程度:[/bold] {cve.severity.value}\n"
            f"[bold]发布日期:[/bold] {cve.published_date}\n"
            f"[bold]描述:[/bold] {cve.description}\n\n"
            f"[bold]修复建议:[/bold] {cve.fix_recommendation}",
            title="📋 CVE 详情",
            box=box.ROUNDED
        ))
        
        if cve.affected_products:
            console.print(f"[bold]受影响产品:[/bold]")
            for product in cve.affected_products[:10]:
                console.print(f"  • {product}")
        
        if cve.references:
            console.print(f"\n[bold]参考链接:[/bold]")
            for ref in cve.references[:5]:
                console.print(f"  🔗 {ref}")
        
    except Exception as e:
        console.print(f"[red]✗ 获取详情失败：{e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--output', '-o', required=True, help='输出文件路径')
@click.option('--limit', '-l', default=None, type=int, help='导出数量限制')
@click.option('--db-path', default=None, help='数据库路径')
def export(output, limit, db_path):
    """导出漏洞库"""
    
    setup_logging(level='INFO')
    
    try:
        db = VulnerabilityDatabase(db_path)
        count = db.export_to_json(output, limit)
        
        console.print(f"[green]✓ 成功导出 {count} 条 CVE 记录到：{output}[/green]")
        
    except Exception as e:
        console.print(f"[red]✗ 导出失败：{e}[/red]")
        sys.exit(1)


@cli.command()
def disclaimer():
    """显示免责声明"""
    print_disclaimer()


def main():
    """主入口"""
    cli()


if __name__ == '__main__':
    main()
