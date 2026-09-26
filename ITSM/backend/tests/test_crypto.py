"""字段级加密单测：Fernet 往返 + 历史明文兼容 + 列类型透明加解密。"""
from sqlalchemy import text

from app.core.crypto import decrypt_field, encrypt_field
from app.models import Outsourcing


def test_encrypt_decrypt_roundtrip():
    secret = "乙方不得泄露甲方数据"
    token = encrypt_field(secret)
    assert token != secret
    assert token.startswith("enc:v1:")
    assert decrypt_field(token) == secret


def test_decrypt_legacy_plaintext_passthrough():
    # 历史明文（无前缀）原样返回，实现无迁移平滑升级
    assert decrypt_field("历史明文") == "历史明文"
    assert decrypt_field("") == ""
    assert decrypt_field(None) is None


def test_encrypt_non_deterministic():
    # Fernet 每次随机 IV，密文不同但均可解密（非确定性，防重放）
    a = encrypt_field("x")
    b = encrypt_field("x")
    assert a != b
    assert decrypt_field(a) == decrypt_field(b) == "x"


def test_encrypted_text_column_transparent(db):
    o = Outsourcing(work_order_id=1, outsource_user_id=1, nda="保密协议原文")
    db.add(o)
    db.commit()

    # ORM 读回自动解密
    assert o.nda == "保密协议原文"

    # 底层落库值为密文（非明文）
    raw = db.execute(text("SELECT nda FROM outsourcing WHERE id = :id"), {"id": o.id}).scalar()
    assert raw.startswith("enc:v1:")
    assert "保密协议原文" not in raw
