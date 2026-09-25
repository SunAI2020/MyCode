"""AI 增强（建议 + 人工确认）：工单摘要 / 工单转知识草稿。

均遵循 §4.16 落地原则：LLM 不可用时确定性降级，不阻塞主流程；转知识仅生成草稿，审核后入库。
"""
from app.models import KbArticle, WorkOrder
from app.services.llm_service import chat, llm_configured


def summarize_work_order(wo: WorkOrder) -> str:
    """工单执行摘要：LLM 生成，未配置/失败降级为确定性模板摘要。"""
    if llm_configured():
        prompt = (
            "请为以下运维工单生成一段简洁的执行摘要（100字内）：\n"
            f"类型：{wo.type}，项目：{wo.project or '—'}，描述：{wo.description or '—'}，"
            f"状态：{wo.status}，进度：{wo.progress}%。"
        )
        try:
            return chat(prompt)
        except Exception:
            pass
    return f"工单 {wo.no}（{wo.type}）：{wo.description or '无描述'}，当前状态 {wo.status}，进度 {wo.progress}%。"


def work_order_to_kb_draft(db, wo: WorkOrder, operator_id: int | None) -> KbArticle:
    """工单转知识草稿：沉淀为知识条目（status=草稿，待审核入库）。"""
    title = f"[{wo.type}] {wo.description[:40] if wo.description else wo.no}"
    content = (
        f"工单号：{wo.no}\n类型：{wo.type}\n项目：{wo.project or '—'}\n"
        f"描述：{wo.description or '—'}\n状态：{wo.status}"
    )
    article = KbArticle(
        title=title,
        category="故障手册",
        content=content,
        status="草稿",
        author_id=operator_id,
    )
    db.add(article)
    db.flush()
    return article
