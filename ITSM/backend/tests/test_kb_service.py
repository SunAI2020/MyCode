"""知识库单测：检索 + 浏览计数。"""
from app.models import KbArticle
from app.services.kb_service import increment_view, search_articles


def _mk(db, title, category="故障手册", content="", status="已发布"):
    a = KbArticle(title=title, category=category, content=content, status=status)
    db.add(a)
    db.flush()
    return a


def test_search_by_keyword(db):
    _mk(db, "MySQL 主从延迟排查", content="复制延迟常见原因")
    _mk(db, "Redis 内存优化", content="淘汰策略")
    db.commit()

    rows = search_articles(db, q="MySQL").all()
    assert [r.title for r in rows] == ["MySQL 主从延迟排查"]


def test_search_by_category(db):
    _mk(db, "漏洞：Log4j", category="漏洞")
    _mk(db, "SOP：驻场巡检", category="SOP")
    db.commit()

    rows = search_articles(db, category="SOP").all()
    assert [r.title for r in rows] == ["SOP：驻场巡检"]


def test_increment_view(db):
    a = _mk(db, "标题")
    db.commit()
    increment_view(db, a)
    increment_view(db, a)
    db.commit()
    assert a.view_count == 2
