"""search normalization and PostgreSQL fuzzy indexes

Revision ID: 55d72af1c901
Revises: 7c31aa8a42f0
"""
from typing import Sequence, Union

from alembic import op

revision: str = "55d72af1c901"
down_revision: Union[str, None] = "7c31aa8a42f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        # Canonical stored values let exact searches use ordinary B-tree indexes.
        op.execute("UPDATE part SET part_no = upper(regexp_replace(part_no, '\\s+', '', 'g'))")
        op.execute("UPDATE part SET oem_no = upper(regexp_replace(oem_no, '\\s+', '', 'g')) WHERE oem_no IS NOT NULL")
    else:
        op.execute("UPDATE part SET part_no = upper(replace(part_no, ' ', ''))")
        op.execute("UPDATE part SET oem_no = upper(replace(oem_no, ' ', '')) WHERE oem_no IS NOT NULL")

    op.create_index("uq_part_part_no", "part", ["part_no"], unique=True)
    op.create_index("ix_machine_brand_model", "machine", ["brand", "model"], unique=False)
    op.create_index("ix_part_active_category", "part", ["is_active", "category"], unique=False)

    if dialect == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute("CREATE INDEX ix_part_name_zh_trgm ON part USING gin (name_zh gin_trgm_ops)")
        op.execute("CREATE INDEX ix_part_name_en_trgm ON part USING gin (name_en gin_trgm_ops)")
        op.execute("CREATE INDEX ix_part_name_vi_trgm ON part USING gin (name_vi gin_trgm_ops)")
        op.execute("CREATE INDEX ix_part_alias_alias_trgm ON part_alias USING gin (alias gin_trgm_ops)")


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_part_alias_alias_trgm")
        op.execute("DROP INDEX IF EXISTS ix_part_name_vi_trgm")
        op.execute("DROP INDEX IF EXISTS ix_part_name_en_trgm")
        op.execute("DROP INDEX IF EXISTS ix_part_name_zh_trgm")
    op.drop_index("ix_part_active_category", table_name="part")
    op.drop_index("ix_machine_brand_model", table_name="machine")
    op.drop_index("uq_part_part_no", table_name="part")
