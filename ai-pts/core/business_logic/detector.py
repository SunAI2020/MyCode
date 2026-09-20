"""
业务逻辑检测器：LLM 语义理解（分类/测试用例生成）+ 确定性差分验证（神经-符号）。
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

from core.business_logic.differential import HttpResponse, analyze_authorization
from core.business_logic.scenarios import ScenarioClassifier, _looks_sensitive


def _url_host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _safe_url(url: str, allowed_hosts: set) -> bool:
    """防 SSRF/提示注入：相对 URL（无主机）视为同源放行；绝对 URL 仅 http/https 且 hostname ∈ allowed_hosts。"""
    try:
        p = urlparse(url)
    except ValueError:
        return False
    if p.scheme and p.scheme not in ("http", "https"):
        return False  # 其它协议（file/ftp/...）拒绝
    host = (p.hostname or "").lower()
    if not host:
        return True  # 相对 URL（如 /orders/100）→ 同源，无 SSRF 风险
    return host in allowed_hosts

Executor = Callable[[str, str, str], HttpResponse]  # (method, url, role) -> response


class BusinessLogicDetector:
    """神经-符号业务逻辑漏洞检测器。"""

    TESTCASE_PROMPT = """你是 Web 业务逻辑安全测试专家。给定敏感端点与业务场景，生成针对 IDOR/BOLA/越权的测试用例。输出 JSON 数组，每项：
{{"method":"GET/POST/...","url":"目标 URL","resource_id":"资源标识值（可空）","expect_denied":true/false,"owner":"owner 角色名","attacker":"attacker 角色名","reason":"测试目的"}}
只返回 JSON 数组。"""

    def __init__(self, llm: Optional[Callable[[str, str], Dict]] = None,
                 executor: Optional[Executor] = None):
        self.llm = llm
        self.executor = executor
        self.classifier = ScenarioClassifier(llm) if llm else None

    def _gen_testcases(self, target: str, endpoints: List[Dict]) -> List[Dict]:
        if not self.llm or not endpoints:
            return []
        user = f"""目标: {target}

敏感端点：
{endpoints}

请生成测试用例。"""
        try:
            result = self.llm(self.TESTCASE_PROMPT, user)
            return result if isinstance(result, list) else []
        except Exception:
            return []

    def run(self, target: str, endpoints: List[Dict], roles: List[str],
            executor: Optional[Executor] = None) -> List[Dict]:
        """执行业务逻辑检测。roles 如 ["owner", "attacker"]。"""
        executor = executor or self.executor
        if not executor:
            return [{"error": "未提供 HTTP 执行器 executor"}]

        if self.classifier:
            classified = self.classifier.classify(endpoints)
        else:
            # 无 LLM 时用确定性兜底标记敏感端点
            classified = [dict(e) for e in endpoints]
            for e in classified:
                e["sensitive"] = _looks_sensitive(e)
        sensitive = [e for e in classified if e.get("sensitive")]
        testcases = self._gen_testcases(target, sensitive)

        # 无 LLM 测试用例时，用确定性兜底：对每个敏感端点做 owner/attacker 差分
        if not testcases and len(roles) >= 2:
            for e in sensitive:
                testcases.append({
                    "method": e.get("method", "GET"),
                    "url": e.get("url"),
                    "resource_id": e.get("resource_id", ""),
                    "expect_denied": False,
                    "owner": roles[0],
                    "attacker": roles[1],
                })

        findings: List[Dict] = []
        scenario_by_url = {e.get("url"): e.get("scenario", "") for e in sensitive}

        # 授权 hostname 白名单（由可信输入 target + endpoints 推导），防 LLM 生成 URL 造成 SSRF
        allowed_hosts = {_url_host(target)}
        for e in endpoints:
            h = _url_host(e.get("url", ""))
            if h:
                allowed_hosts.add(h)
        allowed_hosts.discard("")
        for tc in testcases:
            if not isinstance(tc, dict) or not tc.get("url"):
                continue
            owner_role = tc.get("owner") or (roles[0] if roles else "owner")
            attacker_role = tc.get("attacker") or (roles[1] if len(roles) > 1 else "attacker")
            method = tc.get("method", "GET")
            url = tc["url"]
            if not _safe_url(url, allowed_hosts):
                findings.append({"url": url, "method": method, "finding_type": "blocked",
                                 "reason": "URL 主机不在授权目标范围内，已拦截（防 SSRF）"})
                continue
            try:
                owner_resp = executor(method, url, owner_role)
                attacker_resp = executor(method, url, attacker_role)
            except Exception as e:  # noqa: BLE001
                findings.append({"url": url, "method": method, "finding_type": "error", "reason": str(e)})
                continue
            verdict = analyze_authorization(
                owner_resp, attacker_resp,
                resource_id=str(tc.get("resource_id", "") or ""),
                expect_denied=bool(tc.get("expect_denied", False)),
            )
            if verdict["finding_type"] != "none":
                findings.append({
                    "url": url,
                    "method": method,
                    "finding_type": verdict["finding_type"],
                    "confidence": verdict["confidence"],
                    "reason": verdict["reason"],
                    "scenario": scenario_by_url.get(url, ""),
                })
        return findings
