"""
自主渗透编排器

串联：扫描 → AI 规划攻击路径 → 工具执行 → 结果汇总。
Phase 0 先打通单次闭环；后续在此扩展 agentic loop（每步输出回喂 AI 决策）。
"""
import asyncio
import logging
from typing import Optional, List, Dict, Callable

from core.scanner import create_engine, ScanResult
from core.ai_analyzer import create_analyzer, ScannedService
from core.workflow import create_workflow, WorkflowBuilder, ManualReviewExecutor
from core.executors.getshell import ImpacketExecExecutor, MSFGetShellExecutor
from core.executors.privesc import SecretsDumpExecutor, LinPEASExecutor
from core.executors.lateral import NetExecExecutor, BloodHoundCollector, MimikatzExecutor

logger = logging.getLogger(__name__)


class PenTestOrchestrator:
    """渗透测试编排器：扫描 + AI 规划 + 工具执行"""

    def __init__(
        self,
        api_key: str = None,
        config: dict = None,
        require_confirmation: bool = True,
        whitelist: Optional[List[str]] = None,
        allow_all: bool = False,
        confirm_callback: Optional[Callable[[str], bool]] = None,
    ):
        self.config = config or {}
        self.api_key = api_key
        self.require_confirmation = require_confirmation
        self.whitelist = whitelist or []
        self.allow_all = allow_all
        self.confirm_callback = confirm_callback

        self.scan_engine = create_engine()
        try:
            self.analyzer = create_analyzer(api_key)
        except ValueError:
            self.analyzer = None
            logger.warning("AI 分析器未初始化：无 API key 且环境变量无 CC Switch 通道")

    def scan(self, target: str, ports: str = None) -> ScanResult:
        """执行扫描"""
        return self.scan_engine.scan_sync(target=target, ports=ports)

    @staticmethod
    def _to_ai_services(result: ScanResult) -> List[ScannedService]:
        return [
            ScannedService(
                host_ip=s.host_ip, port=s.port, protocol=s.protocol,
                service_name=s.service_name, product=s.product,
                version=s.version, banner=s.banner,
            )
            for s in result.services
        ]

    def plan(self, services, vulns, target_goal: str = "get_shell"):
        """AI 规划攻击路径；无 API key 时返回 None"""
        if not self.analyzer:
            logger.warning("未配置 API key，无法 AI 规划")
            return None
        return self.analyzer.plan_exploit_path(services, vulns, target_goal)

    @staticmethod
    def _plan_to_dict(plan) -> dict:
        return {
            "plan_id": plan.plan_id,
            "target": plan.target,
            "steps": [
                {
                    "step_id": s.step_id,
                    "exploit_type": s.exploit_type,
                    "target": s.target,
                    "description": s.description,
                    "payload": s.payload,
                    "validation_cmd": s.validation_cmd,
                    "risk_level": s.risk_level,
                }
                for s in plan.steps
            ],
        }

    def build_workflow(self, plan):
        """创建工作流并用真实执行器替换占位符"""
        wf = create_workflow(auto_confirm=not self.require_confirmation)
        kw = dict(
            require_confirmation=self.require_confirmation,
            whitelist=self.whitelist,
            allow_all=self.allow_all,
            confirm_callback=self.confirm_callback,
        )
        wf.executors.register("rce", ImpacketExecExecutor(**kw))
        wf.executors.register("msf", MSFGetShellExecutor(**kw))
        wf.executors.register("privesc", SecretsDumpExecutor(**kw))
        wf.executors.register("privesc_enum", LinPEASExecutor(**kw))
        wf.executors.register("lateral_movement", NetExecExecutor(**kw))
        wf.executors.register("bloodhound", BloodHoundCollector(**kw))
        wf.executors.register("credential_dump", MimikatzExecutor(**kw))
        # 暂无自动化专项工具的漏洞类型：标记需人工验证，避免占位符静默空跑或无执行器中断链
        for t in ("sql_injection", "xss", "auth_bypass", "info_disclosure"):
            wf.executors.register(t, ManualReviewExecutor())
        return wf

    def run(self, target: str, ports: str = None, target_goal: str = "get_shell",
            context: dict = None) -> dict:
        """执行完整流程：扫描 → 规划 → 执行"""
        result = self.scan(target, ports)
        services = self._to_ai_services(result)
        vulns = result.vulnerabilities

        plan = self.plan(services, vulns, target_goal)
        if plan is None:
            return {
                "status": "no_plan",
                "scan": result,
                "vulnerabilities": vulns,
                "message": "未配置 API key，无法 AI 规划攻击路径",
            }

        plan_dict = self._plan_to_dict(plan)
        wf = self.build_workflow(plan)
        steps = WorkflowBuilder.from_ai_plan(plan_dict)
        wf.create_workflow(plan.plan_id, steps)

        wf_result = asyncio.run(wf.execute(context or {}))
        return {
            "status": wf_result.status.value,
            "plan": plan_dict,
            "workflow": wf_result,
            "scan": result,
        }


def create_orchestrator(api_key: str = None, **kwargs) -> PenTestOrchestrator:
    """创建编排器实例"""
    return PenTestOrchestrator(api_key=api_key, **kwargs)


__all__ = ["PenTestOrchestrator", "create_orchestrator"]
