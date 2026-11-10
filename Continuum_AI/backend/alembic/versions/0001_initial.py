"""initial schema

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "claims",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "claim_versions",
        sa.Column("pk", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("claim_id", sa.String(64), nullable=False, index=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "audit_log",
        sa.Column("pk", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "meta",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    for table in ("meta", "audit_log", "claim_versions", "claims", "sources"):
        op.drop_table(table)
