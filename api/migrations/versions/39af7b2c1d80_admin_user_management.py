"""admin user management session version

Revision ID: 39af7b2c1d80
Revises: f5d8a2c4e701
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "39af7b2c1d80"
down_revision: Union[str, None] = "f5d8a2c4e701"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_user", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("admin_user", "auth_version")
