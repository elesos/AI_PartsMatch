"""query log source links and append-only corrections

Revision ID: f5d8a2c4e701
Revises: e4b7c9d1f203
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f5d8a2c4e701"
down_revision: Union[str, None] = "e4b7c9d1f203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("part_query_log", sa.Column("source_id", sa.String(36), nullable=True))
    op.create_index(op.f("ix_part_query_log_source_id"), "part_query_log", ["source_id"])
    op.create_unique_constraint(op.f("uq_part_query_log_query_type"), "part_query_log", ["query_type", "source_id"])
    op.create_table(
        "query_log_correction",
        sa.Column("query_log_id", sa.String(36), nullable=False),
        sa.Column("recommended_part_id", sa.String(36), nullable=True),
        sa.Column("correct_part_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.CheckConstraint("length(trim(reason)) >= 3", name=op.f("ck_query_log_correction_query_log_correction_reason")),
        sa.ForeignKeyConstraint(["actor_id"], ["admin_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["correct_part_id"], ["part.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["query_log_id"], ["part_query_log.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recommended_part_id"], ["part.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("query_log_id"),
    )
    for name in ("query_log_id", "recommended_part_id", "correct_part_id", "actor_id", "status", "created_at"):
        op.create_index(op.f(f"ix_query_log_correction_{name}"), "query_log_correction", [name])
    op.alter_column("knowledge_candidate", "ticket_id", existing_type=sa.String(36), nullable=True)
    op.add_column("knowledge_candidate", sa.Column("query_correction_id", sa.String(36), nullable=True))
    op.create_foreign_key(op.f("fk_knowledge_candidate_query_correction_id_query_log_correction"),
                          "knowledge_candidate", "query_log_correction", ["query_correction_id"], ["id"], ondelete="CASCADE")
    op.create_index(op.f("ix_knowledge_candidate_query_correction_id"), "knowledge_candidate", ["query_correction_id"], unique=True)
    op.create_check_constraint(op.f("ck_knowledge_candidate_knowledge_candidate_single_source"), "knowledge_candidate",
        "(ticket_id IS NOT NULL AND query_correction_id IS NULL) OR (ticket_id IS NULL AND query_correction_id IS NOT NULL)")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_knowledge_candidate_knowledge_candidate_single_source"), "knowledge_candidate", type_="check")
    op.drop_index(op.f("ix_knowledge_candidate_query_correction_id"), table_name="knowledge_candidate")
    op.drop_constraint(op.f("fk_knowledge_candidate_query_correction_id_query_log_correction"), "knowledge_candidate", type_="foreignkey")
    op.drop_column("knowledge_candidate", "query_correction_id")
    op.alter_column("knowledge_candidate", "ticket_id", existing_type=sa.String(36), nullable=False)
    op.drop_table("query_log_correction")
    op.drop_constraint(op.f("uq_part_query_log_query_type"), "part_query_log", type_="unique")
    op.drop_index(op.f("ix_part_query_log_source_id"), table_name="part_query_log")
    op.drop_column("part_query_log", "source_id")
