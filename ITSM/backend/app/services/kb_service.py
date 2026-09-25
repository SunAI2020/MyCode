"""知识库业务逻辑：检索 + 浏览计数。"""
from sqlalchemy.orm import Session

from app.models import KbArticle


def search_articles(
    db: Session,
    q: str | None = None,
    category: str | None = None,
    status: str | None = None,
):
    """关键词全文检索（title/content 不区分大小写子串）+ 分类/状态过滤。"""
    query = db.query(KbArticle)
    if q:
        like = f"%{q}%"
        query = query.filter(KbArticle.title.ilike(like) | KbArticle.content.ilike(like))
    if category is not None:
        query = query.filter(KbArticle.category == category)
    if status is not None:
        query = query.filter(KbArticle.status == status)
    return query


def increment_view(db: Session, article: KbArticle) -> KbArticle:
    """浏览计数自增（支撑高频统计）。"""
    article.view_count += 1
    db.flush()
    return article
