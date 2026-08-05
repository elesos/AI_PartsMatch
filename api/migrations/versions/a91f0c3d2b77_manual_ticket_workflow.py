"""manual ticket workflow, attachments, resolutions and review candidates

Revision ID: a91f0c3d2b77
Revises: c28b91e7d4a2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a91f0c3d2b77"
down_revision: Union[str, None] = "c28b91e7d4a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = [
        sa.Column("owner_key", sa.String(140)), sa.Column("user_id", sa.String(36)),
        sa.Column("country", sa.String(100)), sa.Column("communication_tool", sa.String(30)),
        sa.Column("machine_type", sa.String(100)), sa.Column("machine_brand", sa.String(100)),
        sa.Column("machine_model", sa.String(150)), sa.Column("serial_no", sa.String(150)),
        sa.Column("engine_model", sa.String(150)),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"), sa.Column("note", sa.Text()),
        sa.Column("ai_preliminary_result", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        # api/03 will validate ownership and add an FK once excel_batch exists.
        sa.Column("excel_batch_id", sa.String(36)), sa.Column("assignee_id", sa.String(36)),
        sa.Column("match_evidence", sa.Text()), sa.Column("internal_note", sa.Text()),
    ]
    for column in columns:
        op.add_column("manual_ticket", column)
    op.execute("UPDATE manual_ticket SET owner_key = 'session:' || session_id WHERE session_id IS NOT NULL")
    for name in ("owner_key", "user_id", "machine_brand", "excel_batch_id", "assignee_id"):
        op.create_index(op.f(f"ix_manual_ticket_{name}"), "manual_ticket", [name])
    op.create_foreign_key("fk_manual_ticket_assignee_id_admin_user", "manual_ticket", "admin_user",
                          ["assignee_id"], ["id"], ondelete="SET NULL")

    op.create_table("manual_ticket_attachment",
        sa.Column("ticket_id", sa.String(36), nullable=False), sa.Column("file_id", sa.String(36), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["manual_ticket.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["file_object.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("ticket_id", "file_id"))
    op.create_index(op.f("ix_manual_ticket_attachment_ticket_id"), "manual_ticket_attachment", ["ticket_id"])
    op.create_index(op.f("ix_manual_ticket_attachment_file_id"), "manual_ticket_attachment", ["file_id"])

    op.create_table("manual_ticket_part",
        sa.Column("ticket_id", sa.String(36), nullable=False), sa.Column("part_id", sa.String(36), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_manual_ticket_part_manual_ticket_part_quantity_positive")),
        sa.ForeignKeyConstraint(["ticket_id"], ["manual_ticket.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["part_id"], ["part.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("ticket_id", "part_id"))
    op.create_index(op.f("ix_manual_ticket_part_ticket_id"), "manual_ticket_part", ["ticket_id"])
    op.create_index(op.f("ix_manual_ticket_part_part_id"), "manual_ticket_part", ["part_id"])

    op.create_table("manual_ticket_supplement",
        sa.Column("ticket_id", sa.String(36), nullable=False), sa.Column("content", sa.Text(), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["manual_ticket.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_manual_ticket_supplement_ticket_id"), "manual_ticket_supplement", ["ticket_id"])

    op.create_table("knowledge_candidate",
        sa.Column("ticket_id", sa.String(36), nullable=False), sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["manual_ticket.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("ticket_id"))
    op.create_index(op.f("ix_knowledge_candidate_ticket_id"), "knowledge_candidate", ["ticket_id"], unique=True)
    op.create_index(op.f("ix_knowledge_candidate_status"), "knowledge_candidate", ["status"])

    op.create_table("manual_ticket_cart_addition",
        sa.Column("ticket_id", sa.String(36), nullable=False), sa.Column("owner_key", sa.String(140), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["manual_ticket.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("ticket_id", "owner_key"))
    op.create_index(op.f("ix_manual_ticket_cart_addition_ticket_id"), "manual_ticket_cart_addition", ["ticket_id"])
    op.create_index(op.f("ix_manual_ticket_cart_addition_owner_key"), "manual_ticket_cart_addition", ["owner_key"])


def downgrade() -> None:
    for table in ("manual_ticket_cart_addition", "knowledge_candidate", "manual_ticket_supplement",
                  "manual_ticket_part", "manual_ticket_attachment"):
        op.drop_table(table)
    op.drop_constraint("fk_manual_ticket_assignee_id_admin_user", "manual_ticket", type_="foreignkey")
    for name in ("assignee_id", "excel_batch_id", "machine_brand", "user_id", "owner_key"):
        op.drop_index(op.f(f"ix_manual_ticket_{name}"), table_name="manual_ticket")
    for name in ("internal_note", "match_evidence", "assignee_id", "excel_batch_id", "ai_preliminary_result",
                 "note", "quantity", "engine_model", "serial_no", "machine_model", "machine_brand",
                 "machine_type", "communication_tool", "country", "user_id", "owner_key"):
        op.drop_column("manual_ticket", name)
