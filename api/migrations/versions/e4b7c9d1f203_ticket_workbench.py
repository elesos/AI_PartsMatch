"""ticket workbench timeline and resolution evidence

Revision ID: e4b7c9d1f203
Revises: e4b7c2a9d315
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e4b7c9d1f203"
down_revision: Union[str, None] = "e4b7c2a9d315"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("manual_ticket_part", sa.Column("confidence", sa.Numeric(5, 4), nullable=True))
    op.add_column("manual_ticket_part", sa.Column("reason", sa.Text(), nullable=True))
    op.create_check_constraint(op.f("ck_manual_ticket_part_manual_ticket_part_confidence_range"), "manual_ticket_part", "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)")
    op.create_table(
        "manual_ticket_event",
        sa.Column("ticket_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("status_from", sa.String(30), nullable=True),
        sa.Column("status_to", sa.String(30), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["admin_user.id"], name=op.f("fk_manual_ticket_event_actor_id_admin_user"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ticket_id"], ["manual_ticket.id"], name=op.f("fk_manual_ticket_event_ticket_id_manual_ticket"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_manual_ticket_event")),
    )
    op.create_index(op.f("ix_manual_ticket_event_actor_id"), "manual_ticket_event", ["actor_id"], unique=False)
    op.create_index(op.f("ix_manual_ticket_event_created_at"), "manual_ticket_event", ["created_at"], unique=False)
    op.create_index(op.f("ix_manual_ticket_event_event_type"), "manual_ticket_event", ["event_type"], unique=False)
    op.create_index(op.f("ix_manual_ticket_event_ticket_id"), "manual_ticket_event", ["ticket_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_manual_ticket_event_ticket_id"), table_name="manual_ticket_event")
    op.drop_index(op.f("ix_manual_ticket_event_event_type"), table_name="manual_ticket_event")
    op.drop_index(op.f("ix_manual_ticket_event_created_at"), table_name="manual_ticket_event")
    op.drop_index(op.f("ix_manual_ticket_event_actor_id"), table_name="manual_ticket_event")
    op.drop_table("manual_ticket_event")
    op.drop_constraint(op.f("ck_manual_ticket_part_manual_ticket_part_confidence_range"), "manual_ticket_part", type_="check")
    op.drop_column("manual_ticket_part", "reason")
    op.drop_column("manual_ticket_part", "confidence")
