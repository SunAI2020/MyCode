"""
渗透工作流引擎
执行AI规划的渗透攻击步骤
"""
import asyncio
import logging
import re
import uuid
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod

from core.capabilities import route_ai_steps

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


class WorkflowStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StepInput:
    """步骤输入"""
    target: str
    port: int = 0
    credentials: Dict = field(default_factory=dict)
    context: Dict = field(default_factory=dict)


@dataclass
class StepOutput:
    """步骤输出"""
    status: StepStatus
    result: Any = None
    error: str = ""
    evidence: List[str] = field(default_factory=list)
    execution_time: float = 0.0


@dataclass
class StepResult:
    """单步执行结果"""
    step_id: str
    status: StepStatus
    output: StepOutput
    logs: List[str] = field(default_factory=list)


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    workflow_id: str
    status: WorkflowStatus
    step_results: List[StepResult]
    total_time: float
    success_steps: int
    failed_steps: int
    summary: Dict = field(default_factory=dict)


class BaseExecutor(ABC):
    """执行器基类"""

    @abstractmethod
    async def execute(self, step_input: StepInput, step_config: Dict) -> StepOutput:
        """执行步骤"""
        pass

    @abstractmethod
    async def validate(self, step_input: StepInput) -> bool:
        """验证前置条件"""
        pass

    @abstractmethod
    async def rollback(self, step_output: StepOutput) -> bool:
        """回滚操作"""
        pass


class RCEExecutor(BaseExecutor):
    """远程代码执行执行器"""

    async def execute(self, step_input: StepInput, step_config: Dict) -> StepOutput:
        """执行RCE"""
        logger.info(f"执行RCE: {step_input.target}:{step_input.port}")
        # 实际执行需要集成实际的利用工具
        return StepOutput(
            status=StepStatus.PENDING,
            error="需要配置实际的利用工具"
        )

    async def validate(self, step_input: StepInput) -> bool:
        """验证目标可达"""
        return True

    async def rollback(self, step_output: StepOutput) -> bool:
        """回滚"""
        return True


class SQLInjectionExecutor(BaseExecutor):
    """SQL注入执行器"""

    async def execute(self, step_input: StepInput, step_config: Dict) -> StepOutput:
        logger.info(f"SQL注入: {step_input.target}:{step_input.port}")
        return StepOutput(status=StepStatus.PENDING)

    async def validate(self, step_input: StepInput) -> bool:
        return True

    async def rollback(self, step_output: StepOutput) -> bool:
        return True


class PrivilegeEscalationExecutor(BaseExecutor):
    """权限提升执行器"""

    async def execute(self, step_input: StepInput, step_config: Dict) -> StepOutput:
        logger.info(f"提权: {step_input.target}")
        return StepOutput(status=StepStatus.PENDING)

    async def validate(self, step_input: StepInput) -> bool:
        return True

    async def rollback(self, step_output: StepOutput) -> bool:
        return True


class ManualReviewExecutor(BaseExecutor):
    """暂无自动化专项工具的漏洞类型：标记为 SKIPPED 并提示人工验证"""

    def __init__(self, note: str = "该漏洞类型暂无自动化专项工具，需人工验证"):
        self.note = note

    async def execute(self, step_input: StepInput, step_config: Dict) -> StepOutput:
        logger.info(f"需人工验证: {step_input.target} ({self.note})")
        return StepOutput(status=StepStatus.SKIPPED, error=self.note)

    async def validate(self, step_input: StepInput) -> bool:
        return True

    async def rollback(self, step_output: StepOutput) -> bool:
        return True


class ExecutorRegistry:
    """执行器注册表"""

    def __init__(self):
        self._executors: Dict[str, BaseExecutor] = {}
        self._register_default()

    def _register_default(self):
        """注册默认执行器"""
        self.register("rce", RCEExecutor())
        self.register("sql_injection", SQLInjectionExecutor())
        self.register("privesc", PrivilegeEscalationExecutor())

    def register(self, exploit_type: str, executor: BaseExecutor):
        """注册执行器"""
        self._executors[exploit_type] = executor
        logger.info(f"注册执行器: {exploit_type}")

    def get(self, exploit_type: str) -> Optional[BaseExecutor]:
        """获取执行器"""
        return self._executors.get(exploit_type)

    def list_types(self) -> List[str]:
        """列出所有执行器类型"""
        return list(self._executors.keys())


class ExploitWorkflow:
    """渗透工作流"""

    def __init__(self, auto_confirm: bool = True):
        """
        初始化工作流

        Args:
            auto_confirm: 是否自动确认执行
        """
        self.workflow_id: str = ""
        self.status = WorkflowStatus.CREATED
        self.executors = ExecutorRegistry()
        self.auto_confirm = auto_confirm
        self._steps: List[Dict] = []
        self._results: List[StepResult] = []
        self._current_step: int = 0
        self._paused = False
        self._cancelled = False

    def create_workflow(
        self,
        plan_id: str,
        steps: List[Dict],
        context: Dict = None
    ) -> str:
        """
        创建工作流

        Args:
            plan_id: 计划ID
            steps: 步骤列表（从AI分析获取）
            context: 全局上下文

        Returns:
            str: 工作流ID
        """
        self.workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
        self._steps = steps
        self._results = []
        self._current_step = 0
        self.status = WorkflowStatus.CREATED
        logger.info(f"创建工作流: {self.workflow_id}, {len(steps)} 步骤")
        return self.workflow_id

    async def execute(
        self,
        context: Dict = None,
        callback: Callable[[int, StepResult], None] = None
    ) -> WorkflowResult:
        """
        执行工作流

        Args:
            context: 执行上下文
            callback: 步骤回调

        Returns:
            WorkflowResult: 执行结果
        """
        if not self._steps:
            return self._create_result(WorkflowStatus.FAILED)

        self.status = WorkflowStatus.RUNNING
        start_time = datetime.now()
        ctx = context or {}

        logger.info(f"开始执行工作流: {self.workflow_id}")

        for i, step in enumerate(self._steps):
            if self._cancelled:
                break

            while self._paused:
                await asyncio.sleep(0.5)
                if self._cancelled:
                    break

            # 执行当前步骤
            result = await self._execute_step(i, step, ctx)

            self._results.append(result)

            # 回调
            if callback:
                callback(i, result)

            # 检查结果：单步失败不终止整条链——AI 规划的步骤多为并行尝试，
            # 一个服务不可达（如 SSH 22 关闭、docker 未起）不应掐断其余步骤，
            # 失败在末尾统一汇总（failed_steps / 最终 status）。
            if result.status == StepStatus.FAILED:
                logger.warning(f"步骤 {i+1} 失败，继续执行后续步骤: {result.output.error}")
                if step.get("rollback_on_fail", True):
                    await self._rollback_step(i, result.output)

        # 计算结果
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        success_count = sum(
            1 for r in self._results if r.status == StepStatus.SUCCESS
        )
        failed_count = sum(
            1 for r in self._results if r.status == StepStatus.FAILED
        )

        if self._cancelled:
            self.status = WorkflowStatus.CANCELLED
        elif failed_count > 0:
            self.status = WorkflowStatus.FAILED
        else:
            self.status = WorkflowStatus.COMPLETED

        return WorkflowResult(
            workflow_id=self.workflow_id,
            status=self.status,
            step_results=self._results,
            total_time=total_time,
            success_steps=success_count,
            failed_steps=failed_count,
            summary={
                "total_steps": len(self._steps),
                "success": success_count,
                "failed": failed_count,
                "skipped": len(self._steps) - len(self._results)
            }
        )

    async def _execute_step(
        self,
        index: int,
        step: Dict,
        context: Dict
    ) -> StepResult:
        """执行单个步骤"""
        step_id = step.get("step_id", f"step_{index+1}")
        exploit_type = step.get("exploit_type", "rce")
        target = step.get("target", "")
        tool = step.get("tool") or ""
        logger.info(f"执行步骤 {index+1}: {step_id} [{exploit_type}] tool={tool!r} target={target!r}")

        # 准备输入
        port = context.get(f"{target}_port", 0)

        step_input = StepInput(
            target=target,
            port=port,
            credentials=context.get("credentials", {}),
            context=context
        )

        # 获取执行器
        executor = self.executors.get(exploit_type)

        if not executor:
            logger.error(f"未找到执行器: {exploit_type}")
            return StepResult(
                step_id=step_id,
                status=StepStatus.FAILED,
                output=StepOutput(
                    status=StepStatus.FAILED,
                    error=f"未找到执行器: {exploit_type}"
                )
            )

        # 验证前置条件
        try:
            valid = await executor.validate(step_input)
            if not valid:
                logger.warning(f"前置条件验证失败: {step_id}")
                return StepResult(
                    step_id=step_id,
                    status=StepStatus.SKIPPED,
                    output=StepOutput(
                        status=StepStatus.SKIPPED,
                        error="前置条件不满足"
                    )
                )
        except Exception as e:
            logger.error(f"验证异常: {e}")

        # 执行
        try:
            output = await executor.execute(step_input, step)
            logger.info(f"步骤完成: {step_id}, 状态: {output.status}")
            if output.status == StepStatus.FAILED:
                rc = None
                if isinstance(getattr(output, "result", None), dict):
                    rc = output.result.get("returncode")
                logger.error(f"步骤 {step_id} 失败: {output.error} (returncode={rc})")
            return StepResult(
                step_id=step_id,
                status=output.status,
                output=output
            )
        except Exception as e:
            logger.error(f"执行异常: {e}")
            return StepResult(
                step_id=step_id,
                status=StepStatus.FAILED,
                output=StepOutput(
                    status=StepStatus.FAILED,
                    error=str(e)
                )
            )

    async def _rollback_step(self, index: int, output: StepOutput):
        """回滚步骤"""
        if output and output.result:
            logger.info(f"回滚步骤 {index+1}")
            # 实际回滚需要记录状态

    def pause(self):
        """暂停工作流"""
        self._paused = True
        self.status = WorkflowStatus.PAUSED
        logger.info(f"工作流暂停: {self.workflow_id}")

    def resume(self):
        """恢复工作流"""
        self._paused = False
        self.status = WorkflowStatus.RUNNING
        logger.info(f"工作流恢复: {self.workflow_id}")

    def cancel(self):
        """取消工作流"""
        self._cancelled = True
        self.status = WorkflowStatus.CANCELLED
        logger.info(f"工作流取消: {self.workflow_id}")

    def get_progress(self) -> Dict:
        """获取进度"""
        total = len(self._steps)
        completed = len(self._results)
        progress = (completed / total * 100) if total > 0 else 0

        return {
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "total_steps": total,
            "completed_steps": completed,
            "progress": progress,
            "current_step": self._current_step + 1
        }

    def _create_result(self, status: WorkflowStatus) -> WorkflowResult:
        """创建默认结果"""
        return WorkflowResult(
            workflow_id=self.workflow_id,
            status=status,
            step_results=[],
            total_time=0.0,
            success_steps=0,
            failed_steps=0
        )


class WorkflowBuilder:
    """工作流构建器"""

    @staticmethod
    def from_ai_plan(plan: Dict) -> List[Dict]:
        """
        从AI计划构建工作流步骤

        Args:
            plan: AI返回的计划

        Returns:
            List[Dict]: 工作流步骤
        """
        steps = []
        for step in plan.get("steps", []):
            steps.append({
                "step_id": step.get("step_id", ""),
                "exploit_type": step.get("exploit_type", "rce"),
                "tool": step.get("tool", ""),
                "target": step.get("target", ""),
                "description": step.get("description", ""),
                "payload": step.get("payload", ""),
                "validation_cmd": step.get("validation_cmd", ""),
                "risk_level": step.get("risk_level", "medium"),
                "rollback_on_fail": step.get("risk_level") in ["high", "critical"]
            })
        # 关键词/CVE 兜底路由：修正 AI 输出含糊的 exploit_type / tool
        return route_ai_steps(steps)

    @staticmethod
    def create_manual_workflow(
        steps: List[tuple]
    ) -> List[Dict]:
        """
        创建手动工作流

        Args:
            steps: [(exploit_type, target, description), ...]

        Returns:
            List[Dict]: 工作流步骤
        """
        workflow = []
        for i, (exploit_type, target, description) in enumerate(steps):
            workflow.append({
                "step_id": f"manual_{i+1}",
                "exploit_type": exploit_type,
                "target": target,
                "description": description,
                "risk_level": "medium",
                "rollback_on_fail": True
            })
        return workflow


_HOST_TOKEN_RE = re.compile(r"[A-Za-z0-9.\-]+")


def resolve_step_targets(steps: List[Dict], hosts: List[str]) -> List[Dict]:
    """把 AI/fallback 计划中的描述性 target 归一化为真实主机 IP。

    AI 返回的 step.target 可能是 "目标服务" 之类的描述文本，而执行器的
    _validate_host 只接受 IP/主机名。这里优先从已有 target 中提取合法主机，
    否则回退到扫描发现的主目标主机，避免「含非法字符，拒绝执行」。

    Args:
        steps: WorkflowBuilder.from_ai_plan 产出的步骤列表
        hosts: 扫描发现的主机 IP 列表（可为空）

    Returns:
        就地修改后的 steps（同时返回，便于链式调用）
    """
    primary = (hosts[0] if hosts else "") or ""
    for s in steps:
        t = (s.get("target") or "").strip()
        for prefix in ("http://", "https://"):
            if t.lower().startswith(prefix):
                t = t[len(prefix):]
        host = t.split("/")[0].split(":")[0]
        if host and _HOST_TOKEN_RE.fullmatch(host):
            s["target"] = host
        else:
            s["target"] = primary
    return steps


def create_workflow(auto_confirm: bool = True) -> ExploitWorkflow:
    """创建工作流实例"""
    return ExploitWorkflow(auto_confirm=auto_confirm)


# 测试/示例
if __name__ == "__main__":
    print("渗透工作流模块")
    print("=" * 50)

    # 示例工作流
    workflow = create_workflow()

    # 创建计划
    plan = {
        "steps": [
            {
                "step_id": "step_1",
                "exploit_type": "rce",
                "target": "192.168.1.100:8080",
                "description": "利用Tomcat RCE获取初始shell",
                "payload": "示例命令",
                "risk_level": "high",
                "rollback_on_fail": True
            },
            {
                "step_id": "step_2",
                "exploit_type": "privesc",
                "target": "192.168.1.100",
                "description": "从www-data提权到root",
                "risk_level": "critical",
                "rollback_on_fail": True
            }
        ]
    }

    # 构建工作流
    steps = WorkflowBuilder.from_ai_plan(plan)
    wf_id = workflow.create_workflow("plan_001", steps)

    print(f"\n创建工作流: {wf_id}")
    print(f"  步骤数: {len(steps)}")

    print("\n执行器类型:", workflow.executors.list_types())

    print("\n使用方法:")
    print("""
from core.workflow import create_workflow, WorkflowBuilder

# 创建工作流
workflow = create_workflow()

# 从AI计划构建
steps = WorkflowBuilder.from_ai_plan(ai_plan)
workflow.create_workflow("plan_id", steps)

# 执行工作流
result = await workflow.execute(context)

# 暂停/恢复/取消
workflow.pause()
workflow.resume()
workflow.cancel()

# 获取进度
progress = workflow.get_progress()
""")