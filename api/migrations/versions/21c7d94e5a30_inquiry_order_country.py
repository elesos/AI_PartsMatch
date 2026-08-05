"""add inquiry order country

Revision ID: 21c7d94e5a30
Revises: f19b2c4d8e60
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "21c7d94e5a30"
down_revision: Union[str, None] = "f19b2c4d8e60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("inquiry_order", sa.Column("country", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("inquiry_order", "country")
