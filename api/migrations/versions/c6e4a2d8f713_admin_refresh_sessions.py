"""admin refresh sessions

Revision ID: c6e4a2d8f713
Revises: b7d3f9a1c502
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c6e4a2d8f713"
down_revision: Union[str, None] = "b7d3f9a1c502"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("admin_refresh_token",
        sa.Column("token_hash", sa.String(64), nullable=False), sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["admin_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("token_hash"))
    op.create_index(op.f("ix_admin_refresh_token_token_hash"), "admin_refresh_token", ["token_hash"], unique=True)
    op.create_index(op.f("ix_admin_refresh_token_user_id"), "admin_refresh_token", ["user_id"])
    op.create_index(op.f("ix_admin_refresh_token_expires_at"), "admin_refresh_token", ["expires_at"])


def downgrade() -> None:
    op.drop_table("admin_refresh_token")
