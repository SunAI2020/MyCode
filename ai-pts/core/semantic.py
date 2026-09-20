"""
语义预验证：对规则引擎命中项做 LLM 真/误报判定，降误报。

LLM 不可用/失败时确定性回退：保留原 finding 并标注 verify_status="unverified"，不误删真阳性。
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional


class SemanticVerifier:
    SYSTEM_PROMPT = """你是 Web 漏洞预验证专家。对规则引擎命中的漏洞做真/误报判定，输出 JSON。"""

    def __init__(self, llm: Optional[Callable[[str, str], Dict]] = None):
        self.llm = llm

    def verify(self, findings: List[Dict]) -> List[Dict]:
        """逐条判定 finding 是否真实漏洞，原地标注 verify_status。"""
        out: List[Dict] = []
        for f in findings:
            if not isinstance(f, dict):
                continue
            if not self.llm:
                f["verify_status"] = "unverified"
                out.append(f)
                continue
            user = f"""规则引擎命中项：
{f}

请判定是否真实漏洞。以 JSON 返回：
{{"is_real": true|false, "confidence": "high|medium|low", "reason": "判定理由"}}
只返回 JSON。"""
            try:
                verdict = self.llm(self.SYSTEM_PROMPT, user)
            except Exception:
                verdict = None
            if not isinstance(verdict, dict):
                f["verify_status"] = "unverified"  # LLM 失败 → 回退，不误删
            else:
                f["verify_status"] = "confirmed" if verdict.get("is_real") else "rejected"
                f["verify_confidence"] = verdict.get("confidence", "")
                f["verify_reason"] = verdict.get("reason", "")
            out.append(f)
        return out
