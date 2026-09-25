"""知识库全文检索：Elasticsearch 优先，SQL ilike 降级。"""
from app.core.config import settings
from app.models import KbArticle
from app.schemas.kb import KbArticleOut
from app.services.kb_service import search_articles

_ES_INDEX = "kb_article"
_es = None  # 惰性单例


def _get_es():
    global _es
    if _es is not None:
        return _es
    if not settings.ELASTICSEARCH_URL:
        return None
    try:
        from elasticsearch import Elasticsearch

        _es = Elasticsearch(settings.ELASTICSEARCH_URL)
    except Exception:
        _es = None
    return _es


def es_available() -> bool:
    """ES 是否可用（已配置 + 可 ping 通）。未配置/未安装/不可达均为 False。"""
    es = _get_es()
    if es is None:
        return False
    try:
        return bool(es.ping())
    except Exception:
        return False


def index_kb_article(article: KbArticle) -> None:
    """增量索引（尽力而为；ES 不可用静默跳过，不阻塞主流程）。"""
    es = _get_es()
    if es is None:
        return
    try:
        es.index(
            index=_ES_INDEX,
            id=article.id,
            document={
                "title": article.title,
                "content": article.content,
                "category": article.category,
                "status": article.status,
            },
        )
    except Exception:
        pass


def delete_kb_article(article_id: int) -> None:
    """删除索引（尽力而为）。"""
    es = _get_es()
    if es is None:
        return
    try:
        es.delete(index=_ES_INDEX, id=article_id, ignore=[404])
    except Exception:
        pass


def search_kb(
    db,
    q: str | None = None,
    category: str | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    """返回 {items,total,page,size}（与 paginate 同构）。ES 可用且有关键词走 ES，否则 SQL 降级。"""
    if q and es_available():
        try:
            return _search_kb_es(db, q, category, status, page, size)
        except Exception:
            pass  # 任何 ES 异常回退 SQL
    query = search_articles(db, q, category, status)
    total = query.count()
    rows = query.offset((page - 1) * size).limit(size).all()
    items = [KbArticleOut.model_validate(r).model_dump() for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


def _search_kb_es(db, q, category, status, page, size) -> dict:
    es = _get_es()
    must = [{"multi_match": {"query": q, "fields": ["title^2", "content"]}}]
    filters = []
    if category:
        filters.append({"term": {"category": category}})
    if status:
        filters.append({"term": {"status": status}})
    body = {"query": {"bool": {"must": must, "filter": filters}}}
    res = es.search(
        index=_ES_INDEX, body=body, from_=(page - 1) * size, size=size
    )
    total = res["hits"]["total"]["value"]
    ids = [int(h["_id"]) for h in res["hits"]["hits"]]
    if ids:
        rows = db.query(KbArticle).filter(KbArticle.id.in_(ids)).all()
        by_id = {r.id: r for r in rows}
        ordered = [by_id[i] for i in ids if i in by_id]
    else:
        ordered = []
    items = [KbArticleOut.model_validate(r).model_dump() for r in ordered]
    return {"items": items, "total": total, "page": page, "size": size}
