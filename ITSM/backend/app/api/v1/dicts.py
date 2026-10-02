"""字典枚举：读取 + 新增（用于项目类型等自定义枚举，持久化到 sys_dict）。"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission, require_role
from app.models import SysDict, SysUser
from app.services.audit_service import record
from app.utils.response import ok

router = APIRouter(prefix="/dicts", tags=["字典枚举"])

ROLE = ("sys_admin", "sys_ops", "ticket_mgr")


class DictCreate(BaseModel):
    category: str
    name: str
    code: str | None = None


@router.get("/{category}")
def list_dict(category: str, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    """某类别字典项名称列表（按 id 顺序）。"""
    rows = db.query(SysDict).filter(SysDict.category == category).order_by(SysDict.id).all()
    return ok([r.name for r in rows])


@router.post("")
def create_dict(body: DictCreate, user: SysUser = Depends(require_permission("contract:write")), db: Session = Depends(get_db)):
    """新增字典项（如自定义项目类型）。code 缺省取 name。"""
    if not body.name.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "名称不能为空")
    if db.query(SysDict).filter(SysDict.category == body.category, SysDict.name == body.name).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该字典项已存在")
    code = body.code or body.name
    obj = SysDict(category=body.category, code=code, name=body.name)
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"dict:{body.category}:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok({"id": obj.id, "category": body.category, "code": code, "name": body.name})
