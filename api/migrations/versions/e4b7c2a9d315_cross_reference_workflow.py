"""cross reference workflow fields

Revision ID: e4b7c2a9d315
Revises: c3a8e7f4d210
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4b7c2a9d315"
down_revision: Union[str, None] = "c3a8e7f4d210"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("part_cross_reference", sa.Column("brand", sa.String(100)))
    op.add_column("part_cross_reference", sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("part_cross_reference", sa.Column("source", sa.String(100)))
    op.add_column("part_cross_reference", sa.Column("notes", sa.Text()))
    op.add_column("part_cross_reference", sa.Column("status", sa.String(20), nullable=False, server_default="active"))
    op.create_check_constraint("cross_ref_priority_nonnegative", "part_cross_reference", "priority >= 0")
    op.create_check_constraint("cross_ref_status_valid", "part_cross_reference", "status IN ('pending', 'active', 'inactive', 'rejected')")
    op.create_index(op.f("ix_part_cross_reference_status"), "part_cross_reference", ["status"])
    op.create_index("ix_cross_ref_status_priority", "part_cross_reference", ["status", "priority"])


def downgrade() -> None:
    op.drop_index("ix_cross_ref_status_priority", table_name="part_cross_reference")
    op.drop_index(op.f("ix_part_cross_reference_status"), table_name="part_cross_reference")
    op.drop_constraint("ck_part_cross_reference_cross_ref_status_valid", "part_cross_reference", type_="check")
    op.drop_constraint("ck_part_cross_reference_cross_ref_priority_nonnegative", "part_cross_reference", type_="check")
    for column in ("status", "notes", "source", "priority", "brand"):
        op.drop_column("part_cross_reference", column)
