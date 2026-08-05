"""cart ownership, match metadata, and inquiry snapshots

Revision ID: 8b4d9a6c2e10
Revises: 55d72af1c901
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8b4d9a6c2e10"
down_revision: Union[str, None] = "55d72af1c901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cart_item", sa.Column("owner_key", sa.String(length=140), nullable=True))
    op.add_column("cart_item", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.add_column("cart_item", sa.Column("match_status", sa.String(length=30), server_default="exact", nullable=False))
    op.add_column("cart_item", sa.Column("confidence", sa.Numeric(5, 4), nullable=True))
    op.add_column("cart_item", sa.Column("source", sa.String(length=30), server_default="direct", nullable=False))
    op.add_column("cart_item", sa.Column("need_confirm", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("cart_item", sa.Column("query_id", sa.String(length=36), nullable=True))
    op.execute("UPDATE cart_item SET owner_key = 'session:' || session_id")
    op.alter_column("cart_item", "owner_key", nullable=False)
    op.alter_column("cart_item", "session_id", existing_type=sa.String(length=100), nullable=True)
    op.drop_constraint("uq_cart_item_session_id", "cart_item", type_="unique")
    op.create_unique_constraint("uq_cart_item_owner_key", "cart_item", ["owner_key", "part_id"])
    op.create_check_constraint("cart_item_quantity_positive", "cart_item", "quantity > 0")
    op.create_check_constraint("cart_item_confidence_range", "cart_item", "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)")
    op.create_foreign_key("fk_cart_item_query_id_part_query_log", "cart_item", "part_query_log", ["query_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_cart_item_owner_key"), "cart_item", ["owner_key"])
    op.create_index(op.f("ix_cart_item_user_id"), "cart_item", ["user_id"])
    op.create_index(op.f("ix_cart_item_query_id"), "cart_item", ["query_id"])

    op.create_table(
        "inquiry_order",
        sa.Column("order_no", sa.String(50), nullable=False), sa.Column("owner_key", sa.String(140), nullable=False),
        sa.Column("session_id", sa.String(100)), sa.Column("user_id", sa.String(36)),
        sa.Column("contact_name", sa.String(100), nullable=False), sa.Column("contact_method", sa.String(255), nullable=False),
        sa.Column("communication_tool", sa.String(30), nullable=False), sa.Column("note", sa.Text()),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("total_quantity", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False), sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("total_quantity > 0", name=op.f("ck_inquiry_order_inquiry_order_quantity_positive")),
        sa.CheckConstraint("total_amount >= 0", name=op.f("ck_inquiry_order_inquiry_order_amount_nonnegative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inquiry_order")),
    )
    for column in ("order_no", "owner_key", "session_id", "user_id", "status"):
        op.create_index(op.f(f"ix_inquiry_order_{column}"), "inquiry_order", [column], unique=column == "order_no")
    op.create_table(
        "inquiry_order_item",
        sa.Column("order_id", sa.String(36), nullable=False), sa.Column("part_id", sa.String(36)),
        sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False), sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_inquiry_order_item_inquiry_order_item_quantity_positive")),
        sa.CheckConstraint("unit_price >= 0", name=op.f("ck_inquiry_order_item_inquiry_order_item_price_nonnegative")),
        sa.CheckConstraint("subtotal >= 0", name=op.f("ck_inquiry_order_item_inquiry_order_item_subtotal_nonnegative")),
        sa.ForeignKeyConstraint(["order_id"], ["inquiry_order.id"], name=op.f("fk_inquiry_order_item_order_id_inquiry_order"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["part_id"], ["part.id"], name=op.f("fk_inquiry_order_item_part_id_part"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inquiry_order_item")),
    )
    op.create_index(op.f("ix_inquiry_order_item_order_id"), "inquiry_order_item", ["order_id"])
    op.create_index(op.f("ix_inquiry_order_item_part_id"), "inquiry_order_item", ["part_id"])


def downgrade() -> None:
    op.drop_table("inquiry_order_item")
    op.drop_table("inquiry_order")
    op.drop_index(op.f("ix_cart_item_query_id"), table_name="cart_item")
    op.drop_index(op.f("ix_cart_item_user_id"), table_name="cart_item")
    op.drop_index(op.f("ix_cart_item_owner_key"), table_name="cart_item")
    op.drop_constraint("fk_cart_item_query_id_part_query_log", "cart_item", type_="foreignkey")
    op.drop_constraint(op.f("ck_cart_item_cart_item_confidence_range"), "cart_item", type_="check")
    op.drop_constraint(op.f("ck_cart_item_cart_item_quantity_positive"), "cart_item", type_="check")
    op.drop_constraint("uq_cart_item_owner_key", "cart_item", type_="unique")
    op.create_unique_constraint("uq_cart_item_session_id", "cart_item", ["session_id", "part_id"])
    for column in ("query_id", "need_confirm", "source", "confidence", "match_status", "user_id", "owner_key"):
        op.drop_column("cart_item", column)
    op.alter_column("cart_item", "session_id", existing_type=sa.String(length=100), nullable=False)
