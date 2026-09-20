"""
本地靶场集成测试（C4）：DVWA / Juice Shop 多步攻击成功率回归。

真实靶场测试由环境变量 AI_PTS_TARGET_URL 门控（未设置则跳过），例如：
    AI_PTS_TARGET_URL=http://127.0.0.1:8080 python -m pytest tests/test_integration_target.py -v

回归指标测试用 mock 执行器隔离外部依赖（LLM / 靶场 / 工具），可在任意环境跑，
落地「多步攻击成功率 / 失败率 / 证据化路径只含成功步骤」三项回归指标。
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.orchestrator import PenTestOrchestrator
from core.workflow import create_workflow, StepOutput, StepStatus, BaseExecutor

TARGET_URL = os.environ.get("AI_PTS_TARGET_URL", "").strip()


class _FakeExecutor(BaseExecutor):
    """按脚本化状态序列返回结果的假执行器，记录调用。"""

    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = []

    async def validate(self, step_input):
        return True

    async def execute(self, step_input, step_config):
        status = self.statuses.pop(0) if self.statuses else StepStatus.SUCCESS
        self.calls.append(status)
        return StepOutput(status=status, result={"returncode": 0, "stdout": "ok", "stderr": ""},
                          evidence=["$ fake", "ok", ""], execution_time=0.01)

    async def rollback(self, step_output):
        return True


def _make_agentic_orch(statuses):
    """构造单智能体闭环：脚本化 decision + 假执行器。"""
    class _FakeAnalyzer:
        def decide_next_step(self, ctx, goal):
            if self.n > 0:
                return {"decision": "done", "reason": "done"}
            self.n += 1
            return {"decision": "execute", "exploit_type": "rce", "tool": "wmiexec.py",
                    "target": "10.0.0.1", "reason": "try", "params": {}}

        def summarize_history(self, h):
            return ""

    orch = PenTestOrchestrator(
        config={"agentic": {"max_steps": 20, "goal_types": ["rce", "msf"]}},
        require_confirmation=False, whitelist=[], allow_all=True)
    orch.analyzer = _FakeAnalyzer()
    orch.analyzer.n = 0
    fake = _FakeExecutor(statuses)

    def _fake_build(plan=None):
        wf = create_workflow()
        wf.executors.register("rce", fake)
        return wf

    orch.build_workflow = _fake_build
    return orch, fake


class TestMultiStepSuccessRate(unittest.TestCase):
    """多步攻击成功率回归指标（mock 执行器，无外部依赖）。"""

    def test_all_success_rate_is_1(self):
        orch, fake = _make_agentic_orch([StepStatus.SUCCESS])
        res = orch.run_loop(strategy="agentic", target_goal="get_shell",
                            hosts=["10.0.0.1"], max_steps=5)
        n_success = sum(1 for s in res["steps"] if s.get("status") == "success")
        n_total = len(res["steps"])
        self.assertEqual(n_total, 1)
        self.assertEqual(n_success / n_total, 1.0)
        self.assertEqual(res["status"], "goal_reached")

    def test_partial_failure_rate(self):
        orch, fake = _make_agentic_orch([StepStatus.FAILED])
        res = orch.run_loop(strategy="agentic", target_goal="get_shell",
                            hosts=["10.0.0.1"], max_steps=3)
        n_failed = sum(1 for s in res["steps"] if s.get("status") == "failed")
        self.assertEqual(n_failed, 1)

    def test_run_loop_unknown_strategy_raises(self):
        orch = PenTestOrchestrator(config={}, require_confirmation=False)
        with self.assertRaises(ValueError):
            orch.run_loop(strategy="bogus")


class TestEvidencePathRegression(unittest.TestCase):
    """证据化路径只含成功步骤（与 B5 闭环联动）。"""

    def test_evidence_path_excludes_failed_steps(self):
        from core.report_builder import build_evidence_attack_paths
        steps = [
            {"order": 1, "target": "10.0.0.1", "exploit_type": "getshell",
             "tool": "msf", "status": "success", "evidence": ["ok"]},
            {"order": 2, "target": "10.0.0.1", "exploit_type": "privesc",
             "tool": "peas", "status": "failed", "evidence": ["denied"]},
            {"order": 3, "target": "10.0.0.2", "exploit_type": "credential_dump",
             "tool": "secretsdump", "status": "success", "evidence": ["hash"]},
        ]
        nodes = build_evidence_attack_paths(steps, {}, {})
        self.assertEqual(len(nodes), 2)
        self.assertTrue(all(n["host"] in ("10.0.0.1", "10.0.0.2") for n in nodes))


@unittest.skipUnless(TARGET_URL, "未设置 AI_PTS_TARGET_URL（本地靶场未启动），跳过真实靶场集成测试")
class TestLiveTargetIntegration(unittest.TestCase):
    """对真实本地靶场（DVWA/Juice Shop）的端到端扫描。"""

    def test_scan_live_target(self):
        from core.scanner import create_engine
        engine = create_engine()
        result = engine.scan_sync(target=TARGET_URL)
        # 靶场至少应识别出 HTTP 服务或 Web 发现，否则视为环境未就绪
        self.assertTrue(result.services or result.web_findings or result.vulnerabilities)


if __name__ == "__main__":
    unittest.main()
