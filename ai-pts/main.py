#!/usr/bin/env python3
"""
AI-PTS (AI Penetration Testing System)
主入口 - 整合扫描、AI分析、工作流执行
"""
import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from core import (
    create_analyzer,
    create_workflow,
    WorkflowBuilder,
    ScannedService,
    Vulnerability
)

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """设置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("ai-pts.log", encoding="utf-8")
        ]
    )


class AIPTSystem:
    """AI-PTS 系统"""

    def __init__(self, api_key: str = None, config: dict = None):
        """
        初始化系统

        Args:
            api_key: Claude API密钥
            config: 配置字典
        """
        self.config = config or {}
        self.api_key = api_key
        self.analyzer = None
        self.workflow = None
        self.scan_results = None

    def initialize(self):
        """初始化组件"""
        logger.info("初始化AI-PTS系统...")

        # 初始化AI分析器
        if self.api_key:
            from core.ai_analyzer import create_analyzer
            ai_config = self.config.get("ai", {})
            self.analyzer = create_analyzer(
                api_key=self.api_key,
                model=ai_config.get("model", "claude-sonnet-4-20250514")
            )
            logger.info("AI分析器已初始化")
        else:
            logger.warning("未配置API密钥，AI功能不可用")

        # 初始化工作流
        self.workflow = create_workflow()
        logger.info("工作流引擎已初始化")

    def scan(self, target: str, ports: str = None) -> dict:
        """
        执行扫描

        Args:
            target: 扫描目标
            ports: 端口范围

        Returns:
            dict: 扫描结果
        """
        logger.info(f"开始扫描: {target}")

        # 导入扫描器（复用现有代码）
        try:
            from vuln_scanner.core.engine import create_engine
            scanner = create_engine()
            result = scanner.scan_sync(target=target, ports=ports)
            self.scan_results = result
            logger.info(f"扫描完成: {len(result.hosts)} 主机, {len(result.services)} 服务")
            return result
        except Exception as e:
            logger.error(f"扫描失败: {e}")
            return {}

    def analyze(self, services: list, vulns: list) -> dict:
        """
        AI分析

        Args:
            services: 服务列表
            vulns: 漏洞列表

        Returns:
            dict: 分析结果
        """
        if not self.analyzer:
            return {"error": "AI分析器未初始化"}

        logger.info(f"开始AI分析: {len(services)} 服务, {len(vulns)} 漏洞")

        # 分析扫描结果
        report = self.analyzer.analyze_scan_results(services, vulns)

        return {
            "vulnerabilities": report.vulnerabilities,
            "attack_paths": report.attack_paths,
            "recommendations": report.recommendations,
            "risk_summary": report.risk_summary
        }

    def plan_exploit(
        self,
        services: list,
        vulns: list,
        target_goal: str = "get_shell"
    ) -> dict:
        """
        规划渗透路径

        Args:
            services: 服务列表
            vulns: 漏洞列表
            target_goal: 目标

        Returns:
            dict: 渗透计划
        """
        if not self.analyzer:
            return {"error": "AI分析器未初始化"}

        logger.info(f"规划渗透路径: {target_goal}")

        plan = self.analyzer.plan_exploit_path(services, vulns, target_goal)

        return {
            "plan_id": plan.plan_id,
            "target": plan.target,
            "steps": [
                {
                    "step_id": s.step_id,
                    "order": s.order,
                    "exploit_type": s.exploit_type,
                    "target": s.target,
                    "description": s.description,
                    "risk_level": s.risk_level,
                    "success_probability": s.success_probability
                }
                for s in plan.steps
            ],
            "overall_success_probability": plan.overall_success_probability,
            "estimated_time": plan.estimated_time,
            "risks": plan.risks
        }

    def execute_workflow(self, plan: dict, context: dict = None) -> dict:
        """
        执行渗透工作流

        Args:
            plan: 渗透计划
            context: 执行上下文

        Returns:
            dict: 执行结果
        """
        if not self.workflow:
            return {"error": "工作流未初始化"}

        logger.info(f"执行工作流: {plan.get('plan_id')}")

        # 构建工作流步骤
        steps = WorkflowBuilder.from_ai_plan(plan)
        self.workflow.create_workflow(plan.get("plan_id", "plan"), steps)

        # 执行
        result = asyncio.run(self.workflow.execute(context or {}))

        return {
            "workflow_id": result.workflow_id,
            "status": result.status.value,
            "success_steps": result.success_steps,
            "failed_steps": result.failed_steps,
            "total_time": result.total_time,
            "summary": result.summary
        }

    def generate_payload(
        self,
        vuln: Vulnerability,
        target: ScannedService
    ) -> str:
        """
        生成Payload建议

        Args:
            vuln: 漏洞
            target: 目标服务

        Returns:
            str: Payload建议
        """
        if not self.analyzer:
            return "AI分析器未初始化"

        return self.analyzer.generate_payload(vuln, target)


async def interactive_mode():
    """交互模式"""
    print("="*60)
    print("  AI-PTS (AI Penetration Testing System)")
    print("  输入要扫描的目标 (IP/CIDR/域名)，输入 'quit' 退出")
    print("="*60)
    print()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = input("请输入 Anthropic API Key: ").strip()

    if not api_key:
        print("错误: 需要API密钥")
        return

    system = AIPTSystem(api_key=api_key)
    system.initialize()

    while True:
        target = input("\n扫描目标> ").strip()
        if not target:
            continue
        if target.lower() in ["quit", "exit", "q"]:
            break

        try:
            # 扫描
            print(f"\n[*] 扫描 {target}...")
            scan_result = system.scan(target)

            if not scan_result:
                print("[-] 扫描失败")
                continue

            # 提取服务
            from core.ai_analyzer import ScannedService as AIService, Vulnerability as AIVuln

            services = [
                AIService(
                    host_ip=s.host_ip,
                    port=s.port,
                    service_name=s.service_name,
                    product=s.product,
                    version=s.version,
                    banner=s.banner
                )
                for s in scan_result.services
            ]

            # 匹配漏洞
            from vuln_scanner.scanner.vuln_matcher import VulnMatcher
            matcher = VulnMatcher()
            vulns = matcher.match_all_services(scan_result.services)

            print(f"\n[+] 发现 {len(services)} 个服务, {len(vulns)} 个漏洞")

            if services and vulns:
                # AI分析
                print("\n[*] AI分析中...")
                analysis = system.analyze(services, vulns)
                print(f"\n[+] 发现 {len(analysis.get('vulnerabilities', []))} 个可利用漏洞")
                print(f"[+] 风险级别: {analysis.get('risk_summary', {}).get('overall_risk', 'unknown')}")

                if input("\n是否规划攻击路径? (y/n): ").lower() == "y":
                    plan = system.plan_exploit(services, vulns)
                    print(f"\n[+] 计划ID: {plan.get('plan_id')}")
                    print(f"[+] 预计成功率: {plan.get('overall_success_probability', 0)*100:.1f}%")
                    print(f"[+] 步骤数: {len(plan.get('steps', []))}")

                    for step in plan.get("steps", [])[:3]:
                        print(f"  {step['order']}. [{step['exploit_type']}] {step['description']}")

        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="AI-PTS")
    parser.add_argument("-t", "--target", help="扫描目标")
    parser.add_argument("-p", "--ports", help="端口范围")
    parser.add_argument("-k", "--api-key", help="Anthropic API Key")
    parser.add_argument("--analyze", action="store_true", help="执行AI分析")
    parser.add_argument("--plan", action="store_true", help="规划攻击路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.target:
        # 命令行模式
        api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("错误: 需要设置 --api-key 或 ANTHROPIC_API_KEY 环境变量")
            return

        system = AIPTSystem(api_key=api_key)
        system.initialize()

        # 扫描
        result = system.scan(args.target, args.ports)
        print(f"扫描完成: {result}")

        if args.analyze:
            # 分析
            pass

    else:
        # 交互模式
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()