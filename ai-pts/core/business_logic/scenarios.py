"""
业务场景定义与分类。
"""
from __future__ import annotations

from typing import Callable, Dict, List

SCENARIOS = ["登录认证", "用户注册", "密码管理", "信息查询和维护", "用户注销", "支付及转账"]


class ScenarioClassifier:
    """用 LLM 把发现的端点/请求分类到业务场景，并标记授权敏感端点。"""

    SYSTEM_PROMPT = """你是 Web 业务场景分析专家。给定一组端点/请求，把它们归类到业务场景，并标记哪些是授权敏感端点（可能被 IDOR/BOLA/越权攻击）。输出 JSON。"""

    def __init__(self, llm: Callable[[str, str], Dict]):
        self.llm = llm

    def classify(self, endpoints: List[Dict]) -> List[Dict]:
        """输入 [{method, url, ...}]，输出带 scenario 与 sensitive 标记的列表。"""
        if not endpoints:
            return []
        user = f"""端点列表：
{endpoints}

业务场景（六选一）：{", ".join(SCENARIOS)}

请以 JSON 返回数组，每项：
{{"index": 端点下标, "scenario": "场景名", "sensitive": true/false, "reason": "理由"}}
只返回 JSON 数组。"""
        try:
            result = self.llm(self.SYSTEM_PROMPT, user)
        except Exception:
            result = []

        out = [dict(e) for e in endpoints]
        for e in out:
            e.setdefault("scenario", "")
            e.setdefault("sensitive", _looks_sensitive(e))
        if isinstance(result, list):
            for item in result:
                if not isinstance(item, dict):
                    continue
                idx = item.get("index")
                if isinstance(idx, int) and 0 <= idx < len(out):
                    out[idx]["scenario"] = item.get("scenario", "")
                    out[idx]["sensitive"] = bool(item.get("sensitive", False))
                    out[idx]["reason"] = item.get("reason", "")
        return out


def _looks_sensitive(endpoint: Dict) -> bool:
    """确定性兜底：URL 含资源/用户/账户等关键词即视为敏感端点。"""
    url = (endpoint.get("url") or "").lower()
    return any(k in url for k in ("order", "user", "account", "profile", "pay", "admin", "cart", "id"))
