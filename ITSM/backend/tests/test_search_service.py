"""知识库检索单测：ES 未配置时的 SQL 降级路径。"""
from app.models import KbArticle
from app.services.search_service import es_available, reindex_kb, search_kb


def _mk(db, title, category="故障手册", content="", status="已发布"):
    a = KbArticle(title=title, category=category, content=content, status=status)
    db.add(a)
    db.flush()
    return a


def test_es_unavailable_by_default():
    assert es_available() is False


def test_search_kb_sql_fallback(db):
    _mk(db, "MySQL 主从延迟排查", content="复制延迟常见原因")
    _mk(db, "Redis 内存优化", content="淘汰策略")
    db.commit()

    res = search_kb(db, q="MySQL")
    assert set(res.keys()) == {"items", "total", "page", "size"}
    assert res["total"] == 1
    assert res["items"][0]["title"] == "MySQL 主从延迟排查"


def test_search_kb_category_filter(db):
    _mk(db, "漏洞：Log4j", category="漏洞")
    _mk(db, "SOP：驻场巡检", category="SOP")
    db.commit()

    res = search_kb(db, category="SOP")
    assert res["total"] == 1
    assert res["items"][0]["category"] == "SOP"


def test_reindex_no_es_returns_zero(db):
    _mk(db, "已发布条目", status="已发布")
    db.commit()
    assert reindex_kb(db) == 0  # 无 ES 时回填降级返回 0
