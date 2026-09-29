"""合同新增 service_location 列（服务地点，步骤 49 补强）。

Revision ID: 0024
Revises: 0023
"""
import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("contract")}
    if "service_location" not in cols:
        op.add_column("contract", sa.Column("service_location", sa.String(255), nullable=True))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("contract")}
    if "service_location" in cols:
        op.drop_column("contract", "service_location")
