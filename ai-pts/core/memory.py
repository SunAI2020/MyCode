"""
短期记忆与上下文压缩

Phase 0（记忆 + 单智能体 ReAct 闭环）的短期记忆模块：
- StepRecord：单次 ReAct 迭代的记录（动作、状态、结果、证据）。
- SessionMemory：会话级短期记忆，记录已探测服务/漏洞、已获取凭据/权限、步骤历史，
  并渲染成可供 LLM 决策的紧凑上下文。
- Summarizer：上下文压缩器，历史过长时把旧步骤压缩为摘要字符串（借用 HackSynth 的
  Planner-Summarizer 思路，但 Phase 0 为单智能体，压缩器作为独立组件存在）。

本模块不 import 任何 core 模块，可被 ai_analyzer / orchestrator 安全单向引用。
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# 单条输出在上下文中的最大长度（截断，避免 token 爆炸）
_MAX_OUTPUT_CHARS = 500


def _truncate(s: Any, n: int) -> str:
    """把任意值转为字符串并截断到 n 字符。"""
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + "…(截断)"


@dataclass
class StepRecord:
    """单次 ReAct 迭代的记录（全部字段可 JSON 序列化）。"""

    index: int
    action: Dict[str, Any] = field(default_factory=dict)  # {exploit_type,tool,target,params,reason}
    status: str = ""                                       # success / failed / skipped
    result: Dict[str, Any] = field(default_factory=dict)   # {returncode,stdout,stderr}
    evidence: List[str] = field(default_factory=list)      # [命令, stdout, stderr]（已打码）
    error: str = ""
    reason: str = ""
    execution_time: float = 0.0


def _stdout_of(rec: StepRecord) -> str:
    """从 result 或 evidence 中取 stdout 文本。"""
    out = (rec.result or {}).get("stdout") or ""
    if out:
        return out
    ev = rec.evidence or []
    return ev[1] if len(ev) >= 2 else ""


def _render_step_records(steps: List[StepRecord]) -> List[str]:
    """把若干步骤记录渲染为多行文本（供 to_context 与 Summarizer 共用）。"""
    lines: List[str] = []
    for rec in steps:
        action = rec.action or {}
        etype = action.get("exploit_type", "")
        tool = action.get("tool", "") or ""
        target = action.get("target", "") or ""
        lines.append(f"  [{rec.index}] [{rec.status.upper()}] {etype} {tool} @ {target}".rstrip())
        if rec.reason:
            lines.append(f"       理由: {_truncate(rec.reason, 200)}")
        out = _stdout_of(rec)
        if out:
            lines.append(f"       输出: {_truncate(out, _MAX_OUTPUT_CHARS)}")
        if rec.error:
            lines.append(f"       错误: {_truncate(rec.error, 200)}")
    return lines


class SessionMemory:
    """会话级短期记忆。

    记录：目标、已发现主机/服务/漏洞、已获取凭据与权限、步骤历史、观察记录。
    to_context() 渲染为给 LLM 的紧凑文本；snapshot() 输出可序列化字典供报告/审计。
    """

    def __init__(
        self,
        target_goal: str = "get_shell",
        hosts: Optional[List[str]] = None,
        services: Optional[List[Dict[str, Any]]] = None,
        vulns: Optional[List[Dict[str, Any]]] = None,
    ):
        self.target_goal = target_goal
        self.hosts: List[str] = list(hosts or [])
        self.services: List[Dict[str, Any]] = list(services or [])
        self.vulns: List[Dict[str, Any]] = list(vulns or [])
        self.credentials: Dict[str, Dict[str, str]] = {}  # host -> {username,password,hashes,domain}
        self.privileges: Dict[str, str] = {}              # host -> 权限等级
        self.steps: List[StepRecord] = []
        self.observations: List[str] = []

    # ---- 记录 ----

    def add_step(self, action: Dict[str, Any], step_result: Any) -> StepRecord:
        """记录一步执行结果。

        Args:
            action: 该步的动作描述（exploit_type/tool/target/params/reason）。
            step_result: workflow.execute_step 返回的 StepResult（含 .status/.output）。
        """
        output = getattr(step_result, "output", step_result)
        status = getattr(output, "status", None)
        status_str = getattr(status, "value", None) or str(status)
        rec = StepRecord(
            index=len(self.steps) + 1,
            action=dict(action or {}),
            status=str(status_str),
            result=dict(getattr(output, "result", None) or {}),
            evidence=list(getattr(output, "evidence", None) or []),
            error=str(getattr(output, "error", "") or ""),
            reason=str((action or {}).get("description", "") or (action or {}).get("reason", "") or ""),
            execution_time=float(getattr(output, "execution_time", 0.0) or 0.0),
        )
        self.steps.append(rec)
        return rec

    def record_credential(self, host: str, username: str, password: str = "",
                          hashes: str = "", domain: str = "") -> None:
        """记录某主机已获取的凭据。"""
        self.credentials[host] = {
            "username": username,
            "password": password,
            "hashes": hashes,
            "domain": domain,
        }

    def set_privilege(self, host: str, level: str) -> None:
        """记录某主机已获取的权限等级（unknown/user/admin/system 等）。"""
        self.privileges[host] = level

    def add_observation(self, note: str) -> None:
        """记录一条观察（自由文本）。"""
        self.observations.append(note)

    # ---- 渲染 ----

    def to_context(self) -> str:
        """渲染为给 LLM 决策用的紧凑上下文。"""
        lines = [f"当前目标: {self.target_goal}"]
        if self.hosts:
            lines.append("已发现主机: " + ", ".join(self.hosts))
        if self.services:
            lines.append("已发现服务:")
            for s in self.services:
                host = s.get("host_ip", "")
                port = s.get("port", "")
                svc = s.get("service_name", "") or ""
                prod = s.get("product", "") or ""
                ver = s.get("version", "") or ""
                lines.append(f"  - {host}:{port} {svc} {prod} {ver}".rstrip())
        if self.vulns:
            lines.append("已发现漏洞:")
            for v in self.vulns:
                cve = v.get("cve_id", "")
                sev = v.get("severity", "")
                desc = str(v.get("description", "") or "")
                lines.append(f"  - {cve} [{sev}] {_truncate(desc, 120)}")
        if self.credentials:
            lines.append("已获取凭据:")
            for host, cred in self.credentials.items():
                user = cred.get("username", "")
                if cred.get("hashes"):
                    secret = "hash:***"
                elif cred.get("password"):
                    secret = "pwd:***"
                else:
                    secret = "(无口令)"
                lines.append(f"  - {host} {user} ({secret})")
        if self.privileges:
            lines.append("已获取权限:")
            for host, level in self.privileges.items():
                lines.append(f"  - {host}: {level}")
        if self.observations:
            lines.append("观察记录:")
            for o in self.observations[-10:]:
                lines.append(f"  - {_truncate(o, 200)}")
        if self.steps:
            lines.append("已执行步骤:")
            lines.extend(_render_step_records(self.steps))
        return "\n".join(lines)

    def snapshot(self) -> Dict[str, Any]:
        """输出可序列化快照（供返回/报告/审计）。evidence 已由执行器打码。"""
        return {
            "target_goal": self.target_goal,
            "hosts": list(self.hosts),
            "services": list(self.services),
            "vulns": list(self.vulns),
            "credentials": dict(self.credentials),
            "privileges": dict(self.privileges),
            "observations": list(self.observations),
            "steps": [asdict(r) for r in self.steps],
        }


class Summarizer:
    """上下文压缩器：历史过长时把旧步骤压缩进摘要字符串。"""

    def __init__(
        self,
        summarize_fn: Optional[Callable[[str], str]] = None,
        max_steps: int = 8,
        max_chars: int = 6000,
        keep_recent: int = 3,
    ):
        self.summarize_fn = summarize_fn
        self.max_steps = max_steps
        self.max_chars = max_chars
        self.keep_recent = keep_recent
        self.summary = ""

    def maybe_summarize(self, memory: SessionMemory, context_len: Optional[int] = None) -> None:
        """当步骤数或上下文长度超阈值时，把旧步骤压缩进 self.summary。

        context_len 可选：调用方已渲染过 to_context() 时可传入其长度，避免重复渲染。
        """
        if context_len is None:
            context_len = len(memory.to_context())
        if len(memory.steps) <= self.max_steps and context_len <= self.max_chars:
            return
        if len(memory.steps) <= self.keep_recent:
            return
        old = memory.steps[: -self.keep_recent]
        recent = memory.steps[-self.keep_recent:]
        old_text = "\n".join(_render_step_records(old))
        self.summary = self._summarize(old_text)
        memory.steps = recent

    def _summarize(self, old_text: str) -> str:
        combined = old_text
        if self.summary:
            combined = f"前序摘要:\n{self.summary}\n\n新增步骤:\n{old_text}"
        if self.summarize_fn:
            try:
                s = self.summarize_fn(combined)
                if s and s.strip():
                    return s.strip()
            except Exception as e:  # noqa: BLE001
                logger.warning("摘要调用失败，退化为截断: %s", e)
        # 确定性退化：无 LLM 或失败时，截断保留关键步骤
        return _truncate(combined, 2000)
