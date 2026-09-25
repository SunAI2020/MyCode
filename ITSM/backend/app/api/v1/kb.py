"""知识库：条目 CRUD + 检索 + 浏览计数。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.models import KbArticle, SysUser
from app.schemas.kb import KbArticleCreate, KbArticleOut, KbArticleUpdate
from app.services.audit_service import record
from app.services.kb_service import increment_view
from app.services.search_service import delete_kb_article, index_kb_article, search_kb
from app.utils.response import ok

RW_ROLE = ("sys_admin", "sys_ops", "ticket_mgr")
DEL_ROLE = ("sys_admin", "sys_ops")

router = APIRouter(prefix="/kb-articles", tags=["知识库"])


@router.get("")
def list_articles(
    q: str | None = Query(None),
    category: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*RW_ROLE)),
    db: Session = Depends(get_db),
):
    return ok(search_kb(db, q, category, status, page, size))


@router.post("")
def create_article(
    body: KbArticleCreate,
    user: SysUser = Depends(require_role(*RW_ROLE)),
    db: Session = Depends(get_db),
):
    obj = KbArticle(**body.model_dump(), author_id=user.id)  # 作者取自当前用户，防 mass-assignment 冒名
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"kb_article:{obj.id}", after=str(body.model_dump()))
    db.commit()
    index_kb_article(obj)  # 增量同步 ES 索引（ES 不可用静默跳过）
    return ok(KbArticleOut.model_validate(obj).model_dump())


@router.get("/{aid}")
def get_article(aid: int, user: SysUser = Depends(require_role(*RW_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(KbArticle, aid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识条目不存在")
    return ok(KbArticleOut.model_validate(obj).model_dump())


@router.put("/{aid}")
def update_article(
    aid: int,
    body: KbArticleUpdate,
    user: SysUser = Depends(require_role(*RW_ROLE)),
    db: Session = Depends(get_db),
):
    obj = db.get(KbArticle, aid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识条目不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"kb_article:{aid}", after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    index_kb_article(obj)  # 增量同步 ES 索引
    return ok(KbArticleOut.model_validate(obj).model_dump())


@router.delete("/{aid}")
def delete_article(aid: int, user: SysUser = Depends(require_role(*DEL_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(KbArticle, aid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识条目不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"kb_article:{aid}")
    db.commit()
    delete_kb_article(aid)  # 同步删除 ES 索引
    return ok({"deleted": aid})


@router.post("/{aid}/view")
def view_article(aid: int, user: SysUser = Depends(require_role(*RW_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(KbArticle, aid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识条目不存在")
    increment_view(db, obj)
    db.commit()
    return ok({"view_count": obj.view_count})
