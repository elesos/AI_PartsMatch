"""machine management fields and configurable types

Revision ID: c3a8e7f4d210
Revises: d8f2a4c6e901
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3a8e7f4d210"
down_revision: Union[str, None] = "d8f2a4c6e901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "machine_type",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_machine_type")),
        sa.UniqueConstraint("code", name=op.f("uq_machine_type_code")),
    )
    op.create_index(op.f("ix_machine_type_code"), "machine_type", ["code"], unique=True)
    op.create_index(op.f("ix_machine_type_is_active"), "machine_type", ["is_active"], unique=False)
    machine_types = sa.table(
        "machine_type", sa.column("id", sa.String), sa.column("code", sa.String),
        sa.column("name", sa.String), sa.column("sort_order", sa.Integer), sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(machine_types, [
        {"id": "type-forklift", "code": "forklift", "name": "叉车", "sort_order": 10, "is_active": True},
        {"id": "type-excavator", "code": "excavator", "name": "挖掘机", "sort_order": 20, "is_active": True},
        {"id": "type-loader", "code": "loader", "name": "装载机", "sort_order": 30, "is_active": True},
    ])
    op.execute(sa.text("""
        INSERT INTO machine_type (id, code, name, sort_order, is_active)
        SELECT substr(md5(machine_type), 1, 32), machine_type, machine_type, 100, true
        FROM machine WHERE machine_type <> ''
        ON CONFLICT (code) DO NOTHING
    """))
    op.add_column("machine", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("machine_part_relation", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index(op.f("ix_machine_part_relation_is_active"), "machine_part_relation", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_machine_part_relation_is_active"), table_name="machine_part_relation")
    op.drop_column("machine_part_relation", "is_active")
    op.drop_column("machine", "notes")
    op.drop_index(op.f("ix_machine_type_is_active"), table_name="machine_type")
    op.drop_index(op.f("ix_machine_type_code"), table_name="machine_type")
    op.drop_table("machine_type")
