"""
core.agents 角色单元测试：用注入的 fake llm 隔离 LLM 调用。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agents import (
    BaseAgent,
    PlannerAgent,
    ReconAgent,
    ExploitAgent,
    ValidatorAgent,
    GuardianAgent,
)


def _llm_returns(payload):
    """返回一个 fake llm：记录 (system, user)，返回预设 payload。"""
    calls = []

    def llm(system, user):
        calls.append((system, user))
        return payload

    return llm, calls


def test_planner_expand_prompt_contains_tree():
    llm, calls = _llm_returns({"decision": "expand", "node_id": "root",
                               "sub_goals": [{"goal": "A", "exploit_type": "rce"}], "reason": "r"})
    agent = PlannerAgent(llm)
    out = agent.decide_plan("ctx", "tree")
    assert out["decision"] == "expand"
    assert len(calls) == 1
    assert "攻击树" in calls[0][1]


def test_exploit_agent_passes_through():
    llm, _ = _llm_returns({"decision": "execute", "exploit_type": "rce", "tool": "wmiexec.py",
                           "target": "10.0.0.1", "params": {}, "reason": "r"})
    agent = ExploitAgent(llm)
    out = agent.decide_exploit("ctx", "goal", "rce")
    assert out["exploit_type"] == "rce"
    assert out["tool"] == "wmiexec.py"


def test_guardian_fallback_allows_when_llm_raises():
    def llm(system, user):
        raise RuntimeError("boom")

    agent = GuardianAgent(llm)
    out = agent.check("action")
    assert out["allow"] is True  # 失败默认放行，由确定性层兜底


def test_planner_fallback_stops_when_llm_raises():
    def llm(system, user):
        raise RuntimeError("boom")

    agent = PlannerAgent(llm)
    out = agent.decide_plan("ctx", "tree")
    assert out["decision"] == "stop"


def test_validator_judge():
    llm, _ = _llm_returns({"verdict": "success", "confidence": "high", "reason": "ok"})
    agent = ValidatorAgent(llm)
    out = agent.judge("step", "goal")
    assert out["verdict"] == "success"


def test_base_agent_non_dict_returns_fallback():
    llm, _ = _llm_returns("not a dict")
    agent = BaseAgent(llm, role="test")
    out = agent.decide("prompt")
    assert out["decision"] == "stop"
