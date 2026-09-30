"""合规运营框架 P4：合规证据哈希链。

给 compliance_evidence 增 prev_hash / chain_hash，实现链式防篡改：
每条证据的 chain_hash = SHA256(prev_hash | content_hash | source_type | source_id)，
prev_hash 指向同要求下上一条证据的 chain_hash。任一记录被篡改即断链，可验真。

Revision ID: 0027
Revises: 0026
"""
import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("compliance_evidence")}
    if "prev_hash" not in cols:
        op.add_column("compliance_evidence", sa.Column("prev_hash", sa.String(64), nullable=True))
    if "chain_hash" not in cols:
        op.add_column("compliance_evidence", sa.Column("chain_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("compliance_evidence")}
    if "chain_hash" in cols:
        op.drop_column("compliance_evidence", "chain_hash")
    if "prev_hash" in cols:
        op.drop_column("compliance_evidence", "prev_hash")
