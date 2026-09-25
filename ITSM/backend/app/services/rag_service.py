"""RAG 问答：知识库检索 + 可配置大模型摘要（未配置/失败时降级为检索片段）。

- 仅检索 `status=已发布` 条目，避免泄露草稿；
- LLM 经统一抽象层 `llm_service` 调用，超时/失败回退检索。
"""
from app.services.llm_service import chat, llm_configured
from app.services.search_service import search_kb

TOP_K = 5

_SYSTEM_PROMPT = "你是 IT 运维知识库助手，仅依据给定资料作答，资料不足时说明不确定，不编造。"


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
    if not llm_configured():
        return {
            "answer": "未配置大模型，以下为知识库中相关资料：",
            "sources": sources,
            "mode": "retrieval",
        }
    context = "\n\n".join(f"【{a['title']}】{a['content']}" for a in articles)
    prompt = f"问题：{question}\n\n资料：\n{context}\n\n请基于以上资料简要作答。"
    try:
        answer = chat(prompt, system=_SYSTEM_PROMPT)
        return {"answer": answer, "sources": sources, "mode": "llm"}
    except Exception:
        return {
            "answer": "大模型调用失败，以下为知识库中相关资料：",
            "sources": sources,
            "mode": "retrieval",
        }
