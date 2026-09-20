"""
agentic_loop（Phase 0 单智能体 ReAct 闭环）测试。

mock 策略：用假分析器替换 orch.analyzer（decide_next_step / summarize_history），
用假执行器或真实 ImpacketExecExecutor 替换 build_workflow 注册的执行器。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import PenTestOrchestrator
from core.workflow import create_workflow, StepOutput, StepStatus, BaseExecutor


class _FakeAnalyzer:
    """mock AIAnalyzer：按队列返回决策，耗尽后返回 stop。"""

    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.summaries = []

    def decide_next_step(self, ctx, goal):
        if self.decisions:
            return self.decisions.pop(0)
        return {"decision": "stop", "reason": "no more"}

    def summarize_history(self, text):
        self.summaries.append(text)
        return "SUMMARY"


class _FakeExecutor(BaseExecutor):
    """假执行器：记录调用，按给定状态返回。"""

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


def _make_orch(decisions, status=StepStatus.SUCCESS):
    orch = PenTestOrchestrator(
        config={"agentic": {"max_steps": 20, "goal_types": ["rce", "msf"]}},
        require_confirmation=False, whitelist=[], allow_all=True,
    )
    orch.analyzer = _FakeAnalyzer(decisions)
    fake = _FakeExecutor(status)

    def _fake_build(plan=None):
        wf = create_workflow()
        wf.executors.register("rce", fake)
        return wf

    orch.build_workflow = _fake_build
    return orch, fake


def test_loop_stops_on_done():
    orch, fake = _make_orch([{"decision": "done", "done_reason": "already got shell"}])
    res = orch.agentic_loop(target_goal="get_shell", hosts=["10.0.0.1"], max_steps=5)
    assert res["status"] == "done"
    assert res["steps"] == []
    assert fake.calls == []


def test_loop_stops_at_max_steps_on_failure():
    decision = {"decision": "execute", "exploit_type": "rce", "tool": "wmiexec.py",
                "target": "10.0.0.1", "reason": "try"}
    orch, fake = _make_orch([decision, decision, decision], status=StepStatus.FAILED)
    res = orch.agentic_loop(target_goal="get_shell", hosts=["10.0.0.1"], max_steps=3)
    assert res["status"] == "stopped"
    assert len(res["steps"]) == 3
    assert len(fake.calls) == 3


def test_loop_goal_reached_on_success_and_executor_called():
    orch, fake = _make_orch(
        [{"decision": "execute", "exploit_type": "rce", "tool": "wmiexec.py",
          "target": "10.0.0.1", "reason": "try"}],
        status=StepStatus.SUCCESS,
    )
    res = orch.agentic_loop(target_goal="get_shell", hosts=["10.0.0.1"], max_steps=5)
    assert res["status"] == "goal_reached"
    assert len(res["steps"]) == 1
    assert len(fake.calls) == 1  # execute_step 复用了 executor.execute 路径


def test_loop_no_analyzer_returns_safely():
    orch = PenTestOrchestrator(config={}, require_confirmation=False)
    orch.analyzer = None
    res = orch.agentic_loop()
    assert res["status"] == "no_analyzer"
    assert res["memory"] is None


def test_loop_enforces_whitelist_fail_closed():
    from core.executors.getshell import ImpacketExecExecutor

    orch = PenTestOrchestrator(
        config={"agentic": {"max_steps": 20, "goal_types": ["rce", "msf"]}},
        require_confirmation=False, whitelist=["10.0.0.1"], allow_all=False,
    )
    orch.analyzer = _FakeAnalyzer(
        [{"decision": "execute", "exploit_type": "rce", "tool": "wmiexec.py",
          "target": "192.168.1.1", "reason": "try"}]
    )
    ex = ImpacketExecExecutor(require_confirmation=False, whitelist=["10.0.0.1"], allow_all=False)
    ex._tool_available = lambda tool=None: True  # 跳过工具安装检查，专注测白名单

    def _fake_build(plan=None):
        wf = create_workflow()
        wf.executors.register("rce", ex)
        return wf

    orch.build_workflow = _fake_build
    res = orch.agentic_loop(target_goal="get_shell", hosts=["10.0.0.1"], max_steps=2)
    # 非白名单目标 192.168.1.1 被 validate 拒绝 → skipped，且未真正执行命令
    assert res["steps"][0]["status"] == "skipped"


def test_sanitize_params_rejects_dangerous_command():
    params = {"command": "rm -rf /", "username": "admin", "evil": "x", "shell": "bash; rm -rf /"}
    out = PenTestOrchestrator._sanitize_params(params)
    assert "command" not in out  # 危险命令被丢弃，回退默认 whoami
    assert "shell" not in out    # 非法 shell 被丢弃
    assert "evil" not in out     # 未知键被丢弃
    assert out["username"] == "admin"  # 合法键保留


def test_sanitize_params_allows_safe_values():
    out = PenTestOrchestrator._sanitize_params(
        {"command": "whoami", "protocol": "smb", "peas_path": "/tmp/linpeas.sh"}
    )
    assert out["command"] == "whoami"
    assert out["protocol"] == "smb"
    assert out["peas_path"] == "/tmp/linpeas.sh"


def test_decide_next_step_returns_stop_on_non_object_json():
    # 修复：LLM 返回 JSON 数组/裸字符串（非对象）时，decide_next_step 应回退 stop 而非崩溃
    from types import SimpleNamespace
    from core.ai_analyzer import AIAnalyzer

    analyzer = AIAnalyzer(api_key="test-key", model="test-model")
    fake_block = SimpleNamespace(type="text", text="[]")
    fake_resp = SimpleNamespace(content=[fake_block])
    analyzer.client.messages.create = lambda **kwargs: fake_resp

    out = analyzer.decide_next_step("ctx", "get_shell")
    assert out["decision"] == "stop"


def test_parse_json_response_handles_array():
    # 修复：_parse_json_response 应正确解析 JSON 数组（业务逻辑检测的 LLM 路径依赖此）
    from core.ai_analyzer import AIAnalyzer

    analyzer = AIAnalyzer(api_key="test-key", model="test-model")
    result = analyzer._parse_json_response('[{"index": 0}, {"index": 1}]')
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["index"] == 0
