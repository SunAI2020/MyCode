"""AI 增强端点：智能分类 / 派单建议 / 技能矩阵管理。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.models import EngineerSkill, SysUser
from app.schemas.ai import ClassifyIn, ClassifyOut, EngineerSkillCreate, EngineerSkillOut
from app.services.ai_service import classify_ticket, recommend_assignee
from app.utils.response import ok

router = APIRouter(tags=["AI增强"])
ROLE = ("sys_admin", "sys_ops", "ticket_mgr")


@router.post("/ai/classify")
def classify(body: ClassifyIn, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    return ok(classify_ticket(body.description))


@router.get("/ai/recommend-assignee")
def recommend(
    project: str = Query(...),
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    return ok(recommend_assignee(db, project))


@router.get("/engineer-skills")
def list_skills(user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    rows = db.query(EngineerSkill).order_by(EngineerSkill.id).all()
    return ok([EngineerSkillOut.model_validate(r).model_dump() for r in rows])


@router.post("/engineer-skills")
def create_skill(body: EngineerSkillCreate, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    if db.get(SysUser, body.user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    obj = EngineerSkill(**body.model_dump())
    db.add(obj)
    db.commit()
    return ok(EngineerSkillOut.model_validate(obj).model_dump())


@router.delete("/engineer-skills/{sid}")
def delete_skill(sid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    obj = db.get(EngineerSkill, sid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "技能不存在")
    db.delete(obj)
    db.commit()
    return ok({"deleted": sid})
