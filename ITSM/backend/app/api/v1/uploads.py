"""图片上传：multipart → 本地 uploads/ 存储（签到拍照留证）。"""
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.deps import get_current_user
from app.models import SysUser
from app.utils.response import ok

router = APIRouter(prefix="/uploads", tags=["上传"])

ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("")
def upload(file: UploadFile, user: SysUser = Depends(get_current_user)):
    """上传图片，返回可访问的相对 URL（/uploads/<name>）。"""
    ext = ALLOWED.get(file.content_type)
    if ext is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持 jpg/png/webp 图片")
    data = file.file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "图片不能超过 5MB")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(settings.UPLOAD_DIR, name), "wb") as f:
        f.write(data)
    return ok({"url": f"/uploads/{name}"})
