"""
自主渗透编排器

串联：扫描 → AI 规划攻击路径 → 工具执行 → 结果汇总。
Phase 0 先打通单次闭环；后续在此扩展 agentic loop（每步输出回喂 AI 决策）。
"""
import asyncio
import json
import logging
import re
from typing import Optional, List, Dict, Callable

from core.scanner import create_engine, ScanResult
from core.ai_analyzer import create_analyzer, ScannedService
from core.capabilities import MANUAL_TYPES, route_ai_steps
from core.workflow import create_workflow, WorkflowBuilder, ManualReviewExecutor, resolve_step_targets, StepStatus
from core.memory import SessionMemory, Summarizer
from core.agents import PlannerAgent, ReconAgent, ExploitAgent, ValidatorAgent, GuardianAgent, AttackTree
from core.knowledge import KnowledgeBase
from core.semantic import SemanticVerifier
from core.business_logic import BusinessLogicDetector
from core.executors.getshell import ImpacketExecExecutor, MSFGetShellExecutor
from core.executors.privesc import SecretsDumpExecutor, LinPEASExecutor
from core.executors.lateral import NetExecExecutor, BloodHoundCollector, MimikatzExecutor
from core.executors.sqli import SqlmapExecutor
from core.executors.web_exploit import NucleiExecutor
from core.executors.code_audit import SemgrepExecutor

logger = logging.getLogger(__name__)

# LLM 决策 params 允许的键白名单（其余一律丢弃，防提示注入注入任意字段）
_ALLOWED_PARAM_KEYS = {
    "username", "password", "hashes", "domain",
    "command", "protocol", "module", "exploit", "lhost", "lport", "shell", "peas_path",
}

# 允许 LLM 指定的远程侦察命令（impacket 执行，仅安全只读类；其余丢弃回退默认 whoami）
_SAFE_COMMANDS = {
    "whoami", "hostname", "id", "uname -a", "ifconfig", "ipconfig",
    "systeminfo", "net user", "net localgroup administrators", "ipconfig /all",
}

# 允许的 shell（LinPEAS 执行环境）
_SAFE_SHELLS = {"bash", "sh", "cmd", "powershell"}

# 安全 token / 路径字符集
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
_PATH_RE = re.compile(r"^[A-Za-z0-9_./\-]+$")


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
        credential_callback: Optional[Callable[[str, str], Optional[str]]] = None,
    ):
        self.config = config or {}
        self.api_key = api_key
        self.require_confirmation = require_confirmation
        self.whitelist = whitelist or []
        self.allow_all = allow_all
        self.confirm_callback = confirm_callback
        self.credential_callback = credential_callback

        self.scan_engine = create_engine()
        self.knowledge = KnowledgeBase()
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
                    "tool": s.tool,
                    "target": s.target,
                    "description": s.description,
                    "payload": s.payload,
                    "validation_cmd": s.validation_cmd,
                    "risk_level": s.risk_level,
                }
                for s in plan.steps
            ],
        }

    def build_workflow(self, plan=None):
        """创建工作流并注册真实执行器（plan 参数仅为签名兼容，注册不依赖 plan）。"""
        wf = create_workflow(auto_confirm=not self.require_confirmation)
        kw = dict(
            require_confirmation=self.require_confirmation,
            whitelist=self.whitelist,
            allow_all=self.allow_all,
            confirm_callback=self.confirm_callback,
            credential_callback=self.credential_callback,
        )
        wf.executors.register("rce", ImpacketExecExecutor(**kw))
        wf.executors.register("msf", MSFGetShellExecutor(**kw))
        wf.executors.register("privesc", SecretsDumpExecutor(**kw))
        wf.executors.register("privesc_enum", LinPEASExecutor(**kw))
        wf.executors.register("lateral_movement", NetExecExecutor(**kw))
        wf.executors.register("bloodhound", BloodHoundCollector(**kw))
        wf.executors.register("credential_dump", MimikatzExecutor(**kw))
        wf.executors.register("sql_injection", SqlmapExecutor(**kw))
        wf.executors.register("nuclei", NucleiExecutor(**kw))
        wf.executors.register("code_audit", SemgrepExecutor(**kw))
        # 暂无自动化专项工具的漏洞类型：标记需人工验证，避免占位符静默空跑或无执行器中断链
        for t in MANUAL_TYPES:
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
        # 把 AI 计划的描述性 target 归一化为扫描发现的真实主机 IP
        hosts = sorted({s.host_ip for s in result.services if s.host_ip})
        steps = resolve_step_targets(steps, hosts)
        wf.create_workflow(plan.plan_id, steps)

        wf_result = asyncio.run(wf.execute(context or {}))
        return {
            "status": wf_result.status.value,
            "plan": plan_dict,
            "workflow": wf_result,
            "scan": result,
        }

    # ---- Phase 0：单智能体 ReAct 闭环 ----

    @staticmethod
    def _service_to_dict(s) -> Dict:
        """把 ScannedService 或 dict 归一化为 dict。"""
        if isinstance(s, dict):
            return s
        return {
            "host_ip": getattr(s, "host_ip", ""),
            "port": getattr(s, "port", 0),
            "service_name": getattr(s, "service_name", ""),
            "product": getattr(s, "product", ""),
            "version": getattr(s, "version", ""),
        }

    @staticmethod
    def _vuln_to_dict(v) -> Dict:
        """把 Vulnerability 或 dict 归一化为 dict。"""
        if isinstance(v, dict):
            return v
        return {
            "cve_id": getattr(v, "cve_id", ""),
            "severity": getattr(v, "severity", ""),
            "cvss_score": getattr(v, "cvss_score", 0.0),
            "description": getattr(v, "description", ""),
        }

    @staticmethod
    def _goal_reached(step: Dict, step_result, goal_types) -> bool:
        """确定性判定是否达成目标：目标类型步骤成功。"""
        status = getattr(step_result, "status", None)
        status_val = getattr(status, "value", None) or str(status)
        if status_val != StepStatus.SUCCESS.value:
            return False
        return (step or {}).get("exploit_type", "") in goal_types

    @staticmethod
    def _maybe_note_credential(memory, step: Dict, result) -> None:
        """凭据/提权/横向类步骤成功后，往记忆写入一条观察，便于 LLM 续接。

        结构化凭据提取（record_credential/set_privilege）属 Phase 2，此处先用观察
        文本把「凭据/权限可能已变化」的信号显式喂给 LLM。
        """
        status = getattr(getattr(result, "status", None), "value", None)
        if status == StepStatus.SUCCESS.value and (step or {}).get("exploit_type") in (
            "privesc", "credential_dump", "lateral_movement",
        ):
            memory.add_observation(
                f"{(step or {}).get('tool') or (step or {}).get('exploit_type')} 在 "
                f"{(step or {}).get('target')} 成功，凭据/权限可能已变化，请结合输出续接提权或横向"
            )

    @staticmethod
    def _sanitize_params(params) -> Dict:
        """严格白名单校验 LLM 决策里的 params，丢弃未知键与非法值。

        防「提示注入 → 任意命令执行」：command 仅允许安全侦察命令白名单；
        shell/peas_path 用白名单/字符集校验；exploit/lhost/lport 下游 executor 另有
        严格字符集校验（MSFGetShellExecutor），这里仅保证是字符串。
        """
        if not isinstance(params, dict):
            return {}
        out: Dict[str, str] = {}
        for key, val in params.items():
            if key not in _ALLOWED_PARAM_KEYS or not isinstance(val, str):
                continue
            val = val.strip()
            if not val or len(val) > 500:
                continue
            if key == "command" and val not in _SAFE_COMMANDS:
                continue  # 非法/危险命令丢弃，回退默认 whoami
            if key == "shell" and val not in _SAFE_SHELLS:
                continue
            if key in ("peas_path", "exploit") and not _PATH_RE.fullmatch(val):
                continue
            if key in ("module", "protocol") and not _TOKEN_RE.fullmatch(val):
                continue
            # username/password/hashes/domain/lhost/lport：字符串即可，下游决定如何使用
            out[key] = val
        return out

    def agentic_loop(
        self,
        target_goal: str = "get_shell",
        context: dict = None,
        services: list = None,
        vulns: list = None,
        hosts: list = None,
        max_steps: int = None,
    ) -> dict:
        """单智能体 ReAct 闭环：逐步执行，每步把结果回喂 LLM 决策下一步。

        Args:
            target_goal: 目标（get_shell/get_root/data_access）。
            context: 执行上下文（含 credentials 等）。
            services/vulns/hosts: 扫描结果（可空；空则记忆不含扫描信息）。
            max_steps: 最大步数（默认读 config agentic.max_steps）。

        Returns:
            dict: {status, target_goal, final_decision, steps, memory}。
        """
        if self.analyzer is None:
            logger.warning("未配置 API key，无法运行 agentic loop")
            return {"status": "no_analyzer", "steps": [], "memory": None}

        agentic_cfg = (self.config or {}).get("agentic", {})
        max_steps = max_steps or agentic_cfg.get("max_steps", 20)
        goal_types = set(agentic_cfg.get("goal_types", ["rce", "msf"]))

        memory = SessionMemory(
            target_goal=target_goal,
            hosts=list(hosts or []),
            services=[self._service_to_dict(s) for s in (services or [])],
            vulns=[self._vuln_to_dict(v) for v in (vulns or [])],
        )
        summarizer = Summarizer(
            summarize_fn=self.analyzer.summarize_history,
            max_steps=agentic_cfg.get("summarize_max_steps", 8),
            max_chars=agentic_cfg.get("summarize_max_chars", 6000),
        )
        wf = self.build_workflow(plan=None)

        async def _loop():
            goal_hit = False
            decision = {"decision": "execute", "reason": "开始"}
            for _ in range(max_steps):
                ctx_text = memory.to_context()
                if summarizer.summary:
                    ctx_text = f"{ctx_text}\n\n前序摘要：\n{summarizer.summary}"

                decision = self.analyzer.decide_next_step(ctx_text, target_goal)
                if decision.get("decision") in ("done", "stop"):
                    break

                step = {
                    "exploit_type": decision.get("exploit_type", "rce"),
                    "tool": decision.get("tool", "") or "",
                    "target": decision.get("target", "") or "",
                    "description": decision.get("reason", "") or "",
                    "payload": "",
                    "validation_cmd": "",
                    "risk_level": "medium",
                }
                # 严格白名单校验 LLM 提供的 params，丢弃未知键与非法值（防提示注入）
                step.update(self._sanitize_params(decision.get("params")))

                # 确定性兜底：修正 exploit_type/tool + 归一化 target 为真实主机
                route_ai_steps([step])
                resolve_step_targets([step], memory.hosts)

                result = await wf.execute_step(step, context or {})
                memory.add_step(step, result)
                self._maybe_note_credential(memory, step, result)

                if self._goal_reached(step, result, goal_types):
                    goal_hit = True
                    break

                summarizer.maybe_summarize(memory, len(ctx_text))
            return decision, goal_hit

        decision, goal_hit = asyncio.run(_loop())
        if goal_hit:
            status = "goal_reached"
        elif decision.get("decision") == "done":
            status = "done"
        else:
            status = "stopped"

        snapshot = memory.snapshot()
        return {
            "status": status,
            "target_goal": target_goal,
            "final_decision": decision,
            "steps": snapshot["steps"],
            "memory": snapshot,
        }

    # ---- Phase 1：多智能体角色化 + 攻击树 PTT ----

    def _build_agents(self) -> Dict[str, object]:
        """构建五类角色智能体，统一注入 self.analyzer.call_json 作为 llm。"""
        llm = self.analyzer.call_json
        return {
            "planner": PlannerAgent(llm),
            "recon": ReconAgent(llm),
            "exploit": ExploitAgent(llm),
            "validator": ValidatorAgent(llm),
            "guardian": GuardianAgent(llm),
        }

    @staticmethod
    def _render_step_for_validator(step: Dict, step_result) -> str:
        """把一步执行结果渲染成文本，供 Validator 判定。"""
        status = getattr(step_result, "status", None)
        status_val = getattr(status, "value", None) or str(status)
        output = getattr(step_result, "output", None)
        result = getattr(output, "result", None) or {}
        stdout = str(result.get("stdout") or "")[:500]
        stderr = str(result.get("stderr") or "")[:300]
        error = str(getattr(output, "error", "") or "")
        lines = [
            f"动作: {step.get('exploit_type')} {step.get('tool')} @ {step.get('target')}",
            f"状态: {status_val}",
            f"stdout: {stdout}",
        ]
        if stderr:
            lines.append(f"stderr: {stderr}")
        if error:
            lines.append(f"error: {error}")
        return "\n".join(lines)

    def _rag_context(self, target_goal: str, memory) -> str:
        """构建 RAG 上下文块：目标 + 已知漏洞/服务关键词 → 检索相关知识。"""
        parts = [target_goal]
        for v in (memory.vulns or [])[:5]:
            cve = str(v.get("cve_id", "") or "")
            if cve and not cve.startswith("FINDING:"):
                parts.append(cve)
            parts.append(str(v.get("product", "") or ""))
        for s in (memory.services or [])[:5]:
            parts.append(str(s.get("product", "") or ""))
            parts.append(str(s.get("service_name", "") or ""))
        query = " ".join(x for x in parts if x)
        return self.knowledge.context_for(query)

    def multi_agent_loop(
        self,
        target_goal: str = "get_shell",
        context: dict = None,
        services: list = None,
        vulns: list = None,
        hosts: list = None,
        max_steps: int = None,
    ) -> dict:
        """多智能体 ReAct 闭环：Planner/Recon/Exploit/Validator/Guardian + 攻击树 PTT。

        每轮：Planner 分解/选节点 → Recon/Exploit 决定动作 → Guardian 语义校验 →
        （确定性护栏 +）执行 → Validator 判定 → 更新攻击树节点状态。

        Returns:
            dict: {status, target_goal, tree, steps, memory}。
        """
        if self.analyzer is None:
            logger.warning("未配置 API key，无法运行多智能体闭环")
            return {"status": "no_analyzer", "tree": None, "steps": [], "memory": None}

        agentic_cfg = (self.config or {}).get("agentic", {})
        max_steps = max_steps or agentic_cfg.get("max_steps", 20)
        goal_types = set(agentic_cfg.get("goal_types", ["rce", "msf"]))

        memory = SessionMemory(
            target_goal=target_goal,
            hosts=list(hosts or []),
            services=[self._service_to_dict(s) for s in (services or [])],
            vulns=[self._vuln_to_dict(v) for v in (vulns or [])],
        )
        tree = AttackTree(root_goal=target_goal)
        agents = self._build_agents()
        wf = self.build_workflow(plan=None)

        async def _loop():
            goal_hit = False
            for _ in range(max_steps):
                ctx_text = memory.to_context()
                ctx_text = f"{ctx_text}\n\n{self._rag_context(target_goal, memory)}"
                plan = agents["planner"].decide_plan(ctx_text, tree.to_text())
                decision = str(plan.get("decision") or "stop").lower()

                if decision == "expand":
                    tree.add_children(plan.get("node_id") or "root", plan.get("sub_goals") or [])
                    memory.add_observation(f"Planner 分解：{plan.get('reason', '')}")
                    continue
                if decision in ("done", "stop"):
                    break

                # select（或其它）→ 找节点
                node = tree.find(plan.get("node_id") or "") or tree.next_pending_leaf()
                if node is None:
                    memory.add_observation("无可用攻击树节点，停止")
                    break
                node.state = "active"

                if node.exploit_type == "recon":
                    action = agents["recon"].decide_recon(memory.to_context(), node.goal)
                else:
                    action = agents["exploit"].decide_exploit(
                        memory.to_context(), node.goal, node.exploit_type
                    )

                # Guardian 语义校验（LLM 层）
                guard = agents["guardian"].check(json.dumps(action, ensure_ascii=False))
                if not guard.get("allow", True):
                    memory.add_observation(f"Guardian 拒绝：{guard.get('reason', '')}")
                    node.state = "failed"
                    continue

                # recon 动作：重新扫描，合并进记忆
                if node.exploit_type == "recon" and action.get("decision") == "recon":
                    recon_target = action.get("target") or (memory.hosts[0] if memory.hosts else "")
                    if recon_target:
                        try:
                            scan_result = self.scan_engine.scan_sync(target=recon_target)
                            for s in scan_result.services:
                                memory.services.append(self._service_to_dict(s))
                            for v in scan_result.vulnerabilities:
                                memory.vulns.append(self._vuln_to_dict(v))
                            memory.add_observation(f"已重新扫描 {recon_target}，新增服务/漏洞信息")
                            node.state = "succeeded"
                        except Exception as e:  # noqa: BLE001
                            memory.add_observation(f"重新扫描失败：{e}")
                            node.state = "failed"
                    else:
                        node.state = "failed"
                    continue

                # exploit 动作：构建 step 并执行
                if action.get("decision") not in (None, "execute"):
                    node.state = "failed"
                    memory.add_observation(f"Exploit 跳过：{action.get('reason', '')}")
                    continue

                step = {
                    "exploit_type": action.get("exploit_type") or node.exploit_type or "rce",
                    "tool": action.get("tool", "") or "",
                    "target": action.get("target", "") or "",
                    "description": action.get("reason", "") or "",
                    "payload": "",
                    "validation_cmd": "",
                    "risk_level": "medium",
                }
                step.update(self._sanitize_params(action.get("params")))
                route_ai_steps([step])
                resolve_step_targets([step], memory.hosts)

                result = await wf.execute_step(step, context or {})
                memory.add_step(step, result)
                self._maybe_note_credential(memory, step, result)

                # Validator 语义判定
                verdict = agents["validator"].judge(
                    self._render_step_for_validator(step, result), node.goal
                )
                if str(verdict.get("verdict") or "failed") == "success":
                    node.state = "succeeded"
                else:
                    node.state = "failed"

                if self._goal_reached(step, result, goal_types):
                    goal_hit = True
                    break
            return goal_hit

        goal_hit = asyncio.run(_loop())
        if goal_hit:
            status = "goal_reached"
        elif tree.all_succeeded():
            status = "done"
        else:
            status = "stopped"

        snapshot = memory.snapshot()
        return {
            "status": status,
            "target_goal": target_goal,
            "tree": tree.snapshot(),
            "steps": snapshot["steps"],
            "memory": snapshot,
        }

    # ---- Phase 3：业务逻辑 + 语义检测 ----

    def semantic_verify(self, findings: list) -> list:
        """对规则引擎命中项做 LLM 语义预验证（降误报）。"""
        verifier = SemanticVerifier(self.analyzer.call_json if self.analyzer else None)
        return verifier.verify(findings)

    def business_logic_scan(self, target: str, endpoints: list, roles: list, executor=None) -> list:
        """业务逻辑漏洞检测（神经-符号）。

        Args:
            target: 目标（URL/描述）。
            endpoints: [{method, url, ...}] 发现的端点。
            roles: 角色名列表，如 ["owner", "attacker"]。
            executor: (method, url, role) -> HttpResponse，注入式；缺省则报错。
        """
        detector = BusinessLogicDetector(
            self.analyzer.call_json if self.analyzer else None,
            executor=executor,
        )
        return detector.run(target, endpoints, roles)


def create_orchestrator(api_key: str = None, **kwargs) -> PenTestOrchestrator:
    """创建编排器实例"""
    return PenTestOrchestrator(api_key=api_key, **kwargs)


__all__ = ["PenTestOrchestrator", "create_orchestrator"]
