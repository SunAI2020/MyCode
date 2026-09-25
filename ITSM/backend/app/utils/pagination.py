"""分页查询辅助。"""
from typing import Any


def paginate(q: Any, page: int, size: int, schema: Any) -> dict:
    """对 SQLAlchemy 查询分页，并按 schema 序列化 items。"""
    total = q.count()
    rows = q.offset((page - 1) * size).limit(size).all()
    items = [schema.model_validate(r).model_dump() for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}
