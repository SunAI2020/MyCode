"""
multi_agent_loop（Phase 1 多智能体 + 攻击树）测试。

mock 策略：注入脚本化 5-agent + 假执行器，隔离 LLM 与外部工具。
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import PenTestOrchestrator
from core.workflow import create_workflow, StepOutput, StepStatus, BaseExecutor


class _FakeExecutor(BaseExecutor):
    def __init__(self, status=StepStatus.SUCCESS):
        self.status = status
        self.calls = []

    async def validate(self, step_input):
        return True

    async def execute(self, step_input, step_config):
        self.calls.append(dict(step_config))
        return StepOutput(status=self.status,
                          result={"returncode": 0, "stdout": "ok", "stderr": ""},
                          evidence=["$ fake", "ok", ""], execution_time=0.01)

    async def rollback(self, step_output):
        return True


def _make_agents(planner_decisions, exploit_action=None, verdict="success", allow=True):
    """构造脚本化 5-agent，返回 (agents, validator, guardian)。"""
    planner_queue = list(planner_decisions)

    class _Planner:
        def decide_plan(self, ctx, tree):
            if planner_queue:
                return planner_queue.pop(0)
            return {"decision": "stop"}

    class _Recon:
        def decide_recon(self, ctx, goal):
            return {"decision": "recon", "target": "10.0.0.1"}

    class _Exploit:
        def decide_exploit(self, ctx, goal, ntype):
            return exploit_action or {"decision": "execute", "exploit_type": "rce",
                                      "tool": "wmiexec.py", "target": "10.0.0.1", "params": {}}

    class _Validator:
        def __init__(self):
            self.calls = []

        def judge(self, step_text, goal):
            self.calls.append(step_text)
            return {"verdict": verdict, "confidence": "high", "reason": "r"}

    class _Guardian:
        def __init__(self):
            self.calls = []

        def check(self, action_text):
            self.calls.append(action_text)
            return {"allow": allow, "reason": "r"}

    validator = _Validator()
    guardian = _Guardian()
    agents = {
        "planner": _Planner(),
        "recon": _Recon(),
        "exploit": _Exploit(),
        "validator": validator,
        "guardian": guardian,
    }
    return agents, validator, guardian


def _make_orch(planner_decisions, exploit_action=None, verdict="success",
               allow=True, exec_status=StepStatus.SUCCESS):
    orch = PenTestOrchestrator(
        config={"agentic": {"max_steps": 20, "goal_types": ["rce", "msf"]}},
        require_confirmation=False, whitelist=[], allow_all=True,
    )
    agents, validator, guardian = _make_agents(planner_decisions, exploit_action, verdict, allow)
    orch.analyzer = object()  # 非 None 即可；agents 已注入
    orch._build_agents = lambda: agents
    fake = _FakeExecutor(exec_status)

    def _fake_build(plan=None):
        wf = create_workflow()
        wf.executors.register("rce", fake)
        return wf

    orch.build_workflow = _fake_build
    return orch, fake, validator, guardian


def test_full_chain_goal_reached():
    decisions = [
        {"decision": "expand", "node_id": "root", "sub_goals": [{"goal": "拿 shell", "exploit_type": "rce"}]},
        {"decision": "select", "node_id": "n1"},
    ]
    orch, fake, validator, guardian = _make_orch(decisions, verdict="success")
    res = orch.multi_agent_loop(target_goal="get_shell", hosts=["10.0.0.1"], max_steps=10)
    assert res["status"] == "goal_reached"
    assert len(fake.calls) == 1
    assert len(res["steps"]) == 1
    assert res["tree"]["children"][0]["state"] == "succeeded"
    assert len(guardian.calls) == 1  # Guardian 被调用
    assert len(validator.calls) == 1  # Validator 被调用


def test_guardian_rejects_blocks_execution():
    decisions = [
        {"decision": "expand", "node_id": "root", "sub_goals": [{"goal": "拿 shell", "exploit_type": "rce"}]},
        {"decision": "select", "node_id": "n1"},
    ]
    orch, fake, _, _ = _make_orch(decisions, allow=False)
    res = orch.multi_agent_loop(target_goal="get_shell", hosts=["10.0.0.1"], max_steps=10)
    assert len(fake.calls) == 0  # Guardian 拒绝 → 未执行
    assert res["tree"]["children"][0]["state"] == "failed"


def test_validator_failed_marks_node_failed():
    decisions = [
        {"decision": "expand", "node_id": "root", "sub_goals": [{"goal": "拿 shell", "exploit_type": "rce"}]},
        {"decision": "select", "node_id": "n1"},
    ]
    orch, fake, _, _ = _make_orch(decisions, verdict="failed", exec_status=StepStatus.FAILED)
    res = orch.multi_agent_loop(target_goal="get_shell", hosts=["10.0.0.1"], max_steps=10)
    assert len(fake.calls) == 1  # 执行了
    assert res["tree"]["children"][0]["state"] == "failed"


def test_max_steps_terminates():
    decisions = [{"decision": "expand", "node_id": "root",
                  "sub_goals": [{"goal": "x", "exploit_type": "recon"}]}] * 20
    orch, fake, _, _ = _make_orch(decisions)
    res = orch.multi_agent_loop(target_goal="get_shell", hosts=["10.0.0.1"], max_steps=3)
    assert res["status"] == "stopped"


def test_no_analyzer_returns_safely():
    orch = PenTestOrchestrator(config={}, require_confirmation=False)
    orch.analyzer = None
    res = orch.multi_agent_loop()
    assert res["status"] == "no_analyzer"


def test_recon_node_triggers_rescan():
    decisions = [
        {"decision": "expand", "node_id": "root", "sub_goals": [{"goal": "收集信息", "exploit_type": "recon"}]},
        {"decision": "select", "node_id": "n1"},
    ]
    orch, fake, _, _ = _make_orch(decisions)
    orch.scan_engine = SimpleNamespace(
        scan_sync=lambda target=None: SimpleNamespace(
            services=[SimpleNamespace(host_ip="10.0.0.1", port=80, service_name="http",
                                      product="", version="")],
            vulnerabilities=[],
        )
    )
    res = orch.multi_agent_loop(target_goal="get_shell", hosts=["10.0.0.1"], max_steps=10)
    assert res["tree"]["children"][0]["state"] == "succeeded"
    assert len(fake.calls) == 0  # recon 不走 exploit 执行器
    assert any(s.get("service_name") == "http" for s in res["memory"]["services"])


def test_multi_agent_loop_injects_rag_context():
    recorded = {}

    class _Planner:
        def decide_plan(self, ctx, tree):
            recorded["ctx"] = ctx
            return {"decision": "stop"}

    class _Recon:
        def decide_recon(self, ctx, goal):
            return {"decision": "skip"}

    class _Exploit:
        def decide_exploit(self, ctx, goal, ntype):
            return {"decision": "skip"}

    class _Validator:
        def judge(self, step_text, goal):
            return {"verdict": "failed"}

    class _Guardian:
        def check(self, action_text):
            return {"allow": True}

    agents = {"planner": _Planner(), "recon": _Recon(), "exploit": _Exploit(),
              "validator": _Validator(), "guardian": _Guardian()}

    orch = PenTestOrchestrator(config={}, require_confirmation=False, whitelist=[], allow_all=True)
    orch.analyzer = object()
    orch._build_agents = lambda: agents
    orch.knowledge = SimpleNamespace(context_for=lambda query: "RAG_MARKER_CTX")

    orch.multi_agent_loop(target_goal="get_shell", hosts=["10.0.0.1"], max_steps=2)
    assert "RAG_MARKER_CTX" in recorded["ctx"]
