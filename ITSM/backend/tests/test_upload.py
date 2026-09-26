"""图片上传单测：类型/大小校验 + 落盘。"""
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.uploads import upload
from app.core.config import settings
from app.models import SysUser


def _user(db):
    u = SysUser(username="staff", name="安服", pwd_hash="x")
    db.add(u)
    db.commit()
    return u


def test_upload_image(tmp_path, monkeypatch, db):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    u = _user(db)
    fake = SimpleNamespace(content_type="image/jpeg", file=BytesIO(b"\xff\xd8\xff fake jpeg"))
    data = upload(fake, user=u)["data"]
    assert data["url"].startswith("/uploads/")
    name = data["url"].rsplit("/", 1)[-1]
    assert (tmp_path / name).read_bytes() == b"\xff\xd8\xff fake jpeg"


def test_upload_rejects_non_image(tmp_path, monkeypatch, db):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    u = _user(db)
    fake = SimpleNamespace(content_type="text/plain", file=BytesIO(b"x"))
    with pytest.raises(HTTPException) as exc:
        upload(fake, user=u)
    assert exc.value.status_code == 400


def test_upload_rejects_oversize(tmp_path, monkeypatch, db):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    u = _user(db)
    big = b"0" * (5 * 1024 * 1024 + 1)
    fake = SimpleNamespace(content_type="image/png", file=BytesIO(big))
    with pytest.raises(HTTPException) as exc:
        upload(fake, user=u)
    assert exc.value.status_code == 400
