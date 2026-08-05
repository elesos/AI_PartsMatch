"""image OCR ownership and query metadata

Revision ID: c28b91e7d4a2
Revises: 8b4d9a6c2e10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c28b91e7d4a2"
down_revision: Union[str, None] = "8b4d9a6c2e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("file_object", sa.Column("owner_key", sa.String(140), nullable=True))
    op.add_column("file_object", sa.Column("ocr_text", sa.Text(), nullable=True))
    op.add_column("file_object", sa.Column("ocr_lines", sa.JSON(), nullable=True))
    op.add_column("file_object", sa.Column("image_type", sa.String(40), nullable=True))
    op.add_column("file_object", sa.Column("extracted_info", sa.JSON(), nullable=True))
    op.create_index("ix_file_object_owner_key", "file_object", ["owner_key"])
    op.add_column("part_query_log", sa.Column("raw_input", sa.JSON(), nullable=True))
    op.add_column("part_query_log", sa.Column("extracted_info", sa.JSON(), nullable=True))
    op.add_column("part_query_log", sa.Column("ai_result", sa.JSON(), nullable=True))
    configs = sa.table(
        "sys_configs", sa.column("key", sa.String), sa.column("value", sa.JSON),
        sa.column("value_type", sa.String), sa.column("description", sa.String),
        sa.column("is_secret", sa.Boolean),
    )
    op.bulk_insert(configs, [
        {"key": "ocr.provider", "value": "local_tesseract", "value_type": "str", "description": "OCR provider: local_tesseract, http, or test-only mock", "is_secret": False},
        {"key": "ocr.language", "value": "eng", "value_type": "str", "description": "Installed Tesseract language set", "is_secret": False},
        {"key": "ocr.local_timeout_seconds", "value": 10, "value_type": "float", "description": "Local OCR timeout capped at 10 seconds", "is_secret": False},
        {"key": "ocr.http.timeout_seconds", "value": 10, "value_type": "float", "description": "Remote OCR timeout capped at 10 seconds", "is_secret": False},
        {"key": "ocr.http.endpoint", "value": "", "value_type": "str", "description": "Remote OCR endpoint", "is_secret": False},
        {"key": "ocr.http.api_key", "value": "", "value_type": "str", "description": "Remote OCR API key", "is_secret": True},
        {"key": "ocr.blur_threshold", "value": 0.25, "value_type": "float", "description": "Minimum image edge clarity score", "is_secret": False},
        {"key": "image.classification_threshold", "value": 0.35, "value_type": "float", "description": "Minimum rule classification confidence", "is_secret": False},
        {"key": "image.match_min_confidence", "value": 0.0, "value_type": "float", "description": "Minimum catalogue match confidence", "is_secret": False},
    ])


def downgrade() -> None:
    op.execute(sa.text("""DELETE FROM sys_configs WHERE key IN (
        'ocr.provider', 'ocr.language', 'ocr.local_timeout_seconds', 'ocr.http.timeout_seconds',
        'ocr.http.endpoint', 'ocr.http.api_key', 'ocr.blur_threshold',
        'image.classification_threshold', 'image.match_min_confidence'
    )"""))
    op.drop_column("part_query_log", "ai_result")
    op.drop_column("part_query_log", "extracted_info")
    op.drop_column("part_query_log", "raw_input")
    op.drop_index("ix_file_object_owner_key", table_name="file_object")
    op.drop_column("file_object", "extracted_info")
    op.drop_column("file_object", "image_type")
    op.drop_column("file_object", "ocr_lines")
    op.drop_column("file_object", "ocr_text")
    op.drop_column("file_object", "owner_key")
