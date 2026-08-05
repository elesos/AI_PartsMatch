"""persistent Excel batches, rows and background jobs

Revision ID: d4e5f6a7b8c9
Revises: a91f0c3d2b77
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "a91f0c3d2b77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "excel_batch",
        sa.Column("owner_key", sa.String(140), nullable=False),
        sa.Column("session_id", sa.String(100)), sa.Column("user_id", sa.String(36)),
        sa.Column("file_id", sa.String(36), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("duplicate_rows", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("total_rows >= 0 AND total_rows <= 500", name="ck_excel_batch_excel_batch_row_limit"),
        sa.ForeignKeyConstraint(["file_id"], ["file_object.id"], ondelete="RESTRICT"),
    )
    for name in ("owner_key", "session_id", "user_id", "file_id", "status"):
        op.create_index(op.f(f"ix_excel_batch_{name}"), "excel_batch", [name])

    op.create_table(
        "excel_batch_row",
        sa.Column("batch_id", sa.String(36), nullable=False), sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("raw_content", sa.JSON(), nullable=False), sa.Column("normalized_content", sa.JSON(), nullable=False),
        sa.Column("quantity", sa.Integer()), sa.Column("validation_errors", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("match_status", sa.String(30)), sa.Column("candidates", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("confidence", sa.Numeric(5, 4)), sa.Column("match_reason", sa.Text()),
        sa.Column("suggested_action", sa.String(30)), sa.Column("ticket_id", sa.String(36)),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("row_index > 0", name="ck_excel_batch_row_excel_batch_row_index_positive"),
        sa.CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_excel_batch_row_excel_batch_row_quantity_positive"),
        sa.ForeignKeyConstraint(["batch_id"], ["excel_batch.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["manual_ticket.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("batch_id", "row_index"), sa.UniqueConstraint("ticket_id"),
    )
    for name in ("batch_id", "match_status"):
        op.create_index(op.f(f"ix_excel_batch_row_{name}"), "excel_batch_row", [name])

    op.create_table(
        "excel_batch_job",
        sa.Column("batch_id", sa.String(36), nullable=False), sa.Column("owner_key", sa.String(140), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text()), sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_excel_batch_job_excel_batch_job_attempts_nonnegative"),
        sa.ForeignKeyConstraint(["batch_id"], ["excel_batch.id"], ondelete="CASCADE"),
    )
    for name in ("batch_id", "owner_key", "status"):
        op.create_index(op.f(f"ix_excel_batch_job_{name}"), "excel_batch_job", [name])
    op.create_foreign_key("fk_manual_ticket_excel_batch_id_excel_batch", "manual_ticket", "excel_batch",
                          ["excel_batch_id"], ["id"], ondelete="SET NULL")

    configs = sa.table("sys_configs", sa.column("key", sa.String), sa.column("value", sa.JSON),
                       sa.column("value_type", sa.String), sa.column("description", sa.String), sa.column("is_secret", sa.Boolean))
    op.bulk_insert(configs, [
        {"key": "batch.max_file_bytes", "value": 5242880, "value_type": "int", "description": "Excel upload byte limit", "is_secret": False},
        {"key": "batch.max_rows", "value": 500, "value_type": "int", "description": "Excel data row limit", "is_secret": False},
        {"key": "batch.async_threshold", "value": 50, "value_type": "int", "description": "Rows above this use a persisted job", "is_secret": False},
        {"key": "batch.max_uncompressed_bytes", "value": 20971520, "value_type": "int", "description": "XLSX expanded size guard", "is_secret": False},
        {"key": "batch.max_zip_ratio", "value": 100, "value_type": "int", "description": "XLSX zip compression ratio guard", "is_secret": False},
        {"key": "batch.max_job_attempts", "value": 3, "value_type": "int", "description": "Maximum persisted job attempts", "is_secret": False},
        {"key": "batch.template_example", "value": {"设备类型": "叉车", "设备品牌": "Toyota", "整机型号": "8FD30", "Part Number": "12345-67890", "所需数量": 2}, "value_type": "json", "description": "Excel template example row", "is_secret": False},
    ])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM sys_configs WHERE key LIKE 'batch.%'"))
    op.drop_constraint("fk_manual_ticket_excel_batch_id_excel_batch", "manual_ticket", type_="foreignkey")
    op.drop_table("excel_batch_job")
    op.drop_table("excel_batch_row")
    op.drop_table("excel_batch")
