"""parts management fields and image types

Revision ID: d8f2a4c6e901
Revises: c6e4a2d8f713
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d8f2a4c6e901"
down_revision: Union[str, None] = "c6e4a2d8f713"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("part", sa.Column("alternate_no", sa.String(length=150), nullable=True))
    op.add_column("part", sa.Column("stock_status", sa.String(length=30), nullable=False, server_default="in_stock"))
    op.add_column("part", sa.Column("unit", sa.String(length=30), nullable=False, server_default="件"))
    op.add_column("part", sa.Column("notes", sa.Text(), nullable=True))
    op.create_index(op.f("ix_part_alternate_no"), "part", ["alternate_no"], unique=False)
    op.create_index(op.f("ix_part_stock_status"), "part", ["stock_status"], unique=False)
    op.add_column("part_image", sa.Column("image_type", sa.String(length=30), nullable=False, server_default="product"))


def downgrade() -> None:
    op.drop_column("part_image", "image_type")
    op.drop_index(op.f("ix_part_stock_status"), table_name="part")
    op.drop_index(op.f("ix_part_alternate_no"), table_name="part")
    op.drop_column("part", "notes")
    op.drop_column("part", "unit")
    op.drop_column("part", "stock_status")
    op.drop_column("part", "alternate_no")
