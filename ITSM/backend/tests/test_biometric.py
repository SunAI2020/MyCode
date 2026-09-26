"""人脸识别登录（预留）单测。"""
import pytest
from fastapi import HTTPException

from app.api.v1.auth import BiometricLogin, biometric_login


def test_biometric_not_enabled():
    with pytest.raises(HTTPException) as exc:
        biometric_login(BiometricLogin(username="admin", face_token="tok"))
    assert exc.value.status_code == 501  # 未接入人脸 SDK → 明确不支持
