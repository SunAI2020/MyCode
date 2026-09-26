"""服务对象依赖拓扑：cmdb_ci_dependency

Revision ID: 0018
Revises: 0017
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("cmdb_ci_dependency")
