"""add part categories

Revision ID: 7c31aa8a42f0
Revises: 0e1983312174
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "7c31aa8a42f0"
down_revision: Union[str, None] = "0e1983312174"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint("ck_part_part_price_nonnegative", "part", "price IS NULL OR price >= 0")
    op.create_check_constraint("ck_part_part_stock_nonnegative", "part", "stock >= 0")
    op.create_check_constraint("ck_machine_part_relation_machine_part_priority_nonnegative", "machine_part_relation", "priority >= 0")
    op.create_check_constraint("ck_part_cross_reference_cross_ref_distinct_parts", "part_cross_reference", "source_part_id <> target_part_id")
    op.create_check_constraint("ck_part_cross_reference_cross_ref_reliability_range", "part_cross_reference", "reliability >= 0 AND reliability <= 1")
    op.create_table(
        "part_category",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["part_category.id"], name=op.f("fk_part_category_parent_id_part_category"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_part_category")),
    )
    op.create_index(op.f("ix_part_category_is_active"), "part_category", ["is_active"], unique=False)
    op.create_index(op.f("ix_part_category_parent_id"), "part_category", ["parent_id"], unique=False)
    op.create_index(op.f("ix_part_category_slug"), "part_category", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_part_category_slug"), table_name="part_category")
    op.drop_index(op.f("ix_part_category_parent_id"), table_name="part_category")
    op.drop_index(op.f("ix_part_category_is_active"), table_name="part_category")
    op.drop_table("part_category")
    op.drop_constraint("ck_part_cross_reference_cross_ref_reliability_range", "part_cross_reference", type_="check")
    op.drop_constraint("ck_part_cross_reference_cross_ref_distinct_parts", "part_cross_reference", type_="check")
    op.drop_constraint("ck_machine_part_relation_machine_part_priority_nonnegative", "machine_part_relation", type_="check")
    op.drop_constraint("ck_part_part_stock_nonnegative", "part", type_="check")
    op.drop_constraint("ck_part_part_price_nonnegative", "part", type_="check")
