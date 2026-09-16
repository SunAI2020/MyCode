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
        self.orchestrator = None
        self.scan_results = None

    def initialize(self):
        """初始化组件"""
        logger.info("初始化AI-PTS系统...")

        # 初始化AI分析器（api_key 可空，回退本机 CC Switch 环境变量）
        from core.ai_analyzer import create_analyzer
        try:
            ai_config = self.config.get("ai", {})
            self.analyzer = create_analyzer(
                api_key=self.api_key,
                model=ai_config.get("model"),
            )
            logger.info("AI分析器已初始化")
        except ValueError as e:
            self.analyzer = None
            logger.warning(f"AI分析器未初始化: {e}")

        # 初始化工作流
        self.workflow = create_workflow()
        logger.info("工作流引擎已初始化")

        # 初始化渗透编排器（接入 getshell/提权/横向移动 真实执行器）
        from core.orchestrator import create_orchestrator
        self.orchestrator = create_orchestrator(
            api_key=self.api_key,
            config=self.config,
            require_confirmation=True,
        )
        logger.info("渗透编排器已初始化")

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

        # 导入扫描器（自包含适配层，封装 vendored ai-vuln 引擎）
        try:
            from core.scanner import create_engine
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

    def execute_workflow(
        self,
        plan: dict,
        context: dict = None,
        whitelist: list = None,
        confirm_callback=None,
        require_confirmation: bool = True,
    ) -> dict:
        """
        执行渗透工作流（接入真实专项执行器：getshell/提权/横向移动）

        Args:
            plan: 渗透计划
            context: 执行上下文（含 credentials 等）
            whitelist: 目标白名单（空列表且非 allow_all 时 fail-closed）
            confirm_callback: 人工确认回调，签名 (host: str) -> bool
            require_confirmation: 是否强制人工确认

        Returns:
            dict: 执行结果
        """
        if not self.orchestrator:
            return {"error": "渗透编排器未初始化"}

        logger.info(f"执行工作流: {plan.get('plan_id')}")

        # 用真实执行器构建工作流（运行时白名单/确认闸门在此注入）
        from core.orchestrator import create_orchestrator
        orch = create_orchestrator(
            api_key=self.api_key,
            config=self.config,
            require_confirmation=require_confirmation,
            whitelist=whitelist or [],
            confirm_callback=confirm_callback,
        )

        # 构建工作流步骤（把 AI 计划的描述性 target 归一化为真实主机 IP）
        from core.workflow import resolve_step_targets
        steps = WorkflowBuilder.from_ai_plan(plan)
        steps = resolve_step_targets(steps, whitelist or [])
        wf = orch.build_workflow(plan)
        wf.create_workflow(plan.get("plan_id", "plan"), steps)

        # 执行
        result = asyncio.run(wf.execute(context or {}))

        return {
            "workflow_id": result.workflow_id,
            "status": result.status.value,
            "success_steps": result.success_steps,
            "failed_steps": result.failed_steps,
            "total_time": result.total_time,
            "summary": result.summary,
            "step_results": [
                {
                    "step_id": r.step_id,
                    "status": r.status.value,
                    "error": r.output.error,
                    "evidence": r.output.evidence,
                }
                for r in result.step_results
            ],
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


def interactive_mode():
    """交互模式"""
    print("="*60)
    print("  AI-PTS (AI Penetration Testing System)")
    print("  输入要扫描的目标 (IP/CIDR/域名)，输入 'quit' 退出")
    print("="*60)
    print()

    # 认证密钥：优先环境变量（本机 CC Switch 通道），否则交互输入，允许留空
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        api_key = input("请输入 Anthropic API Key（留空使用本机 CC Switch 通道）: ").strip()

    system = AIPTSystem(api_key=api_key or None)
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
            from core.ai_analyzer import ScannedService as AIService

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

            # 漏洞：引擎已在扫描阶段完成 CVE 匹配/设备/蜜罐/去重/富化
            vulns = scan_result.vulnerabilities

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
                        order = step.get("order", step.get("step_id", "?"))
                        print(f"  {order}. [{step.get('exploit_type')}] {step.get('description')}")

                    if input("\n是否执行攻击链? (y/n): ").lower() == "y":
                        _execute_chain(system, plan, scan_result)

        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()


def _execute_chain(system: AIPTSystem, plan: dict, scan_result) -> None:
    """交互式执行攻击链：收集白名单/凭据，逐目标人工确认"""
    hosts = sorted({s.host_ip for s in scan_result.services if s.host_ip})
    if not hosts:
        print("[-] 无目标主机，无法执行攻击链")
        return

    print(f"[!] 目标白名单: {', '.join(hosts)}")
    print("[!] 每个目标执行前都会再次人工确认；工具未安装会跳过")

    creds_raw = input("目标凭据 user:pass（留空使用默认 administrator）: ").strip()
    creds = {}
    if creds_raw:
        if ":" in creds_raw:
            u, _, p = creds_raw.partition(":")
            creds = {"username": u, "password": p}
        else:
            creds = {"username": creds_raw}

    def confirm(host: str) -> bool:
        return input(f"  [!] 确认对 {host} 执行? (y/n): ").lower() == "y"

    print("\n[*] 执行攻击链中...")
    result = system.execute_workflow(
        plan,
        context={"credentials": creds},
        whitelist=hosts,
        confirm_callback=confirm,
        require_confirmation=True,
    )

    print(f"\n[+] 执行状态: {result.get('status')}")
    print(f"[+] 成功 {result.get('success_steps')} 步 / 失败 {result.get('failed_steps')} 步")
    for sr in result.get("step_results", []):
        line = f"  [{sr['status']}] {sr['step_id']}"
        if sr.get("error"):
            line += f" - {sr['error']}"
        print(line)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="AI-PTS")
    parser.add_argument("-t", "--target", help="扫描目标")
    parser.add_argument("-p", "--ports", help="端口范围")
    parser.add_argument("-k", "--api-key", help="Anthropic API Key")
    parser.add_argument("--analyze", action="store_true", help="执行AI分析")
    parser.add_argument("--plan", action="store_true", help="规划攻击路径")
    parser.add_argument("--execute", action="store_true",
                        help="执行攻击链（需配合 --plan；依赖 tools 白名单，未配置将 fail-closed）")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.target:
        # 命令行模式（api_key 允许为空：回退本机 CC Switch 环境变量通道）
        api_key = (
            args.api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        )

        from config import load_config
        cfg = load_config()

        system = AIPTSystem(api_key=api_key or None, config=cfg)
        system.initialize()

        # 扫描
        result = system.scan(args.target, args.ports)
        if not result:
            print("扫描失败")
            return

        services = [
            ScannedService(
                host_ip=s.host_ip,
                port=s.port,
                service_name=s.service_name,
                product=s.product,
                version=s.version,
                banner=s.banner,
            )
            for s in result.services
        ]
        vulns = result.vulnerabilities

        print(f"扫描完成: {len(result.hosts)} 主机, {len(services)} 服务, {len(vulns)} 漏洞")

        if args.analyze:
            analysis = system.analyze(services, vulns)
            print(f"AI分析: 风险 {analysis.get('risk_summary', {}).get('overall_risk', 'unknown')}")

        if args.plan or args.execute:
            plan = system.plan_exploit(services, vulns)
            print(f"攻击路径: {plan.get('plan_id')}, {len(plan.get('steps', []))} 步")
            for step in plan.get("steps", []):
                order = step.get("order", step.get("step_id", "?"))
                print(f"  {order}. [{step.get('exploit_type')}] {step.get('description')}")

            if args.execute:
                # 白名单/确认策略来自 config tools 段；未配置白名单且非 allow_all 时 fail-closed
                tools_cfg = cfg.get("tools", {})
                from core.orchestrator import create_orchestrator
                orch = create_orchestrator(
                    api_key=api_key,
                    config=cfg,
                    require_confirmation=tools_cfg.get("require_confirmation", True),
                    whitelist=tools_cfg.get("whitelist", []),
                    allow_all=tools_cfg.get("allow_all", False),
                )
                steps = WorkflowBuilder.from_ai_plan(plan)
                from core.workflow import resolve_step_targets
                hosts = sorted({s.host_ip for s in result.services if s.host_ip})
                steps = resolve_step_targets(steps, hosts)
                wf = orch.build_workflow(plan)
                wf.create_workflow(plan.get("plan_id", "plan"), steps)
                wf_result = asyncio.run(wf.execute({}))
                print(f"执行状态: {wf_result.status.value} "
                      f"(成功 {wf_result.success_steps} / 失败 {wf_result.failed_steps})")
                for r in wf_result.step_results:
                    detail = f" - {r.output.error}" if r.output.error else ""
                    print(f"  [{r.status.value}] {r.step_id}{detail}")

    else:
        # 交互模式
        interactive_mode()


if __name__ == "__main__":
    main()