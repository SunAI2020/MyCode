"""RAG 问答单测：无 LLM 降级检索 + 仅发布条目。"""
from app.models import KbArticle
from app.services.rag_service import answer_question


def _mk(db, title, content="", status="已发布"):
    a = KbArticle(title=title, category="故障手册", content=content, status=status)
    db.add(a)
    db.flush()
    return a


def test_rag_retrieval_fallback_no_llm(db):
    _mk(db, "MySQL 主从延迟排查", content="复制延迟常见原因")
    _mk(db, "Redis 内存优化", content="淘汰策略")
    db.commit()

    res = answer_question(db, "MySQL")
    assert res["mode"] == "retrieval"  # 未配置 LLM 走检索降级
    assert any("MySQL" in s["title"] for s in res["sources"])


def test_rag_excludes_drafts(db):
    _mk(db, "已发布条目", status="已发布")
    _mk(db, "草稿条目", status="草稿")
    db.commit()

    res = answer_question(db, "条目")
    titles = [s["title"] for s in res["sources"]]
    assert "已发布条目" in titles
    assert "草稿条目" not in titles


def test_rag_no_match(db):
    res = answer_question(db, "不存在的内容")
    assert res["sources"] == []
    assert res["mode"] == "retrieval"
