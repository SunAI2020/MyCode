"""测试夹具：SQLite 内存库 + 会话。"""
import os

# 测试无需真实 DB；为满足 config.Settings 的必填 DATABASE_URL，注入占位值
os.environ.setdefault("DATABASE_URL", "sqlite:///")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  触发模型注册
from app.db.base import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()
    engine.dispose()
