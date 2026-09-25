"""统一 LLM 抽象层：OpenAI 兼容 chat completion。

- 配置项 `LLM_API_BASE`/`LLM_API_KEY`/`LLM_MODEL`（§4.16 可切换厂商，统一 OpenAI 兼容 API）；
- 未配置或调用失败抛异常，由调用方降级（建议 + 人工确认，不阻塞主流程）。
"""
import json
import urllib.request

from app.core.config import settings

DEFAULT_SYSTEM = "你是 IT 运维平台智能助手，仅依据给定信息作答，不编造。"


def llm_configured() -> bool:
    return bool(settings.LLM_API_BASE and settings.LLM_API_KEY)


def chat(prompt: str, system: str | None = None) -> str:
    """调用大模型返回文本；未配置或失败抛异常。"""
    if not llm_configured():
        raise RuntimeError("大模型未配置")
    url = settings.LLM_API_BASE.rstrip("/") + "/chat/completions"
    messages = [
        {"role": "system", "content": system or DEFAULT_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    payload = {
        "model": settings.LLM_MODEL or "gpt-3.5-turbo",
        "messages": messages,
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]
