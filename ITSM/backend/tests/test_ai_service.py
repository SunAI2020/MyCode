"""AI 增强单测：工单摘要降级 / 工单转知识草稿。"""
from app.models import KbArticle, WorkOrder
from app.services.ai_service import summarize_work_order, work_order_to_kb_draft


def _mk_wo(db, description="系统无法登录"):
    wo = WorkOrder(no="WO-2026-2001", type="客户工单", description=description)
    db.add(wo)
    db.flush()
    return wo


def test_summarize_work_order_fallback(db):
    wo = _mk_wo(db)
    db.commit()
    s = summarize_work_order(wo)
    assert "WO-2026-2001" in s  # 无 LLM 时降级模板摘要含工单号
    assert wo.description in s


def test_work_order_to_kb_draft(db):
    wo = _mk_wo(db, description="MySQL 主从延迟")
    db.commit()
    a = work_order_to_kb_draft(db, wo, operator_id=7)
    db.commit()
    assert a.status == "草稿"
    assert a.author_id == 7
    assert "MySQL 主从延迟" in a.title
    assert db.query(KbArticle).count() == 1
