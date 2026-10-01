"""认证接口：登录 / 当前用户信息。"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import _client_ip, customer_scope_of, get_current_user, get_db, permission_codes_of, role_rows_of
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.models import SysUser
from app.schemas.auth import LoginRequest, RoleBrief, TokenResponse, UserOut
from app.services.audit_service import record
from app.utils.response import ok

router = APIRouter(prefix="/auth", tags=["认证"])


def _user_out(user: SysUser, db: Session) -> UserOut:
    roles = [RoleBrief(code=r.code, name=r.name, scope=r.scope) for r in role_rows_of(user, db)]
    return UserOut(
        id=user.id,
        username=user.username,
        name=user.name,
        phone=user.phone,
        dept=user.dept,
        status=user.status,
        roles=roles,
        permissions=sorted(permission_codes_of(user, db)),
        customer_id=customer_scope_of(user, db),
    )


@router.post("/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(SysUser).filter(SysUser.username == req.username).first()
    if user is None or not verify_password(req.password, user.pwd_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")

    token = create_access_token(user.id)
    record(db, user_id=user.id, action="login", resource="auth", ip=_client_ip(request))
    db.commit()
    return ok(TokenResponse(access_token=token, user=_user_out(user, db)).model_dump())


@router.get("/me")
def me(user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(_user_out(user, db).model_dump())


class BiometricLogin(BaseModel):
    username: str
    face_token: str


@router.post("/biometric")
def biometric_login(req: BiometricLogin):
    """人脸识别登录（预留）：未接入人脸比对 SDK 时明确返回不支持。"""
    if not settings.FACE_VERIFY_ENABLED:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "人脸识别未启用（需接入人脸比对 SDK）")
    # 预留：调用人脸比对 SDK（阿里云实人认证/腾讯云人脸核身）核验 req.face_token
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "人脸识别服务未接入")
