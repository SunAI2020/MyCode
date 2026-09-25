"""RAG 问答：知识库检索 + 可配置大模型摘要（未配置/失败时降级为检索片段）。

- 仅检索 `status=已发布` 条目，避免泄露草稿；
- LLM 经 OpenAI 兼容 API 调用（stdlib urllib，不新增依赖），超时/失败回退检索。
"""
import json
import urllib.request

from app.core.config import settings
from app.services.search_service import search_kb

TOP_K = 5

_SYSTEM_PROMPT = "你是 IT 运维知识库助手，仅依据给定资料作答，资料不足时说明不确定，不编造。"


def _llm_configured() -> bool:
    return bool(settings.LLM_API_BASE and settings.LLM_API_KEY)


def _call_llm(prompt: str) -> str:
    url = settings.LLM_API_BASE.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.LLM_MODEL or "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
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


def _sources(articles: list[dict]) -> list[dict]:
    return [
        {"id": a["id"], "title": a["title"], "excerpt": (a.get("content") or "")[:200]}
        for a in articles
    ]


def answer_question(db, question: str) -> dict:
    """返回 {answer, sources, mode}；mode ∈ {llm, retrieval}。"""
    res = search_kb(db, q=question, status="已发布", size=TOP_K)
    articles = res["items"]
    sources = _sources(articles)
    if not articles:
        return {"answer": "未在知识库中找到相关资料。", "sources": [], "mode": "retrieval"}
    if not _llm_configured():
        return {
            "answer": "未配置大模型，以下为知识库中相关资料：",
            "sources": sources,
            "mode": "retrieval",
        }
    context = "\n\n".join(f"【{a['title']}】{a['content']}" for a in articles)
    prompt = f"问题：{question}\n\n资料：\n{context}\n\n请基于以上资料简要作答。"
    try:
        answer = _call_llm(prompt)
        return {"answer": answer, "sources": sources, "mode": "llm"}
    except Exception:
        return {
            "answer": "大模型调用失败，以下为知识库中相关资料：",
            "sources": sources,
            "mode": "retrieval",
        }
