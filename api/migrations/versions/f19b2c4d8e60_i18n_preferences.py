"""internationalization preferences and runtime configuration

Revision ID: f19b2c4d8e60
Revises: e7a6c4b2d901
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f19b2c4d8e60"
down_revision: Union[str, None] = "e7a6c4b2d901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "language_preference",
        sa.Column("owner_key", sa.String(140), nullable=False),
        sa.Column("session_id", sa.String(100)),
        sa.Column("user_id", sa.String(36)),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("language IN ('zh', 'en', 'vi')", name="ck_language_preference_language_preference_supported"),
        sa.UniqueConstraint("owner_key", name="uq_language_preference_owner_key"),
    )
    for column in ("owner_key", "session_id", "user_id"):
        op.create_index(op.f(f"ix_language_preference_{column}"), "language_preference", [column])

    configs = sa.table("sys_configs", sa.column("key", sa.String), sa.column("value", sa.JSON),
                       sa.column("value_type", sa.String), sa.column("description", sa.String),
                       sa.column("is_secret", sa.Boolean))
    op.bulk_insert(configs, [
        {"key": "i18n.messages", "value": {}, "value_type": "json", "description": "Per-language message overrides", "is_secret": False},
        {"key": "i18n.cookie_name", "value": "partsmatch_lang", "value_type": "string", "description": "Language preference cookie name", "is_secret": False},
        {"key": "i18n.cookie_max_age", "value": 31536000, "value_type": "int", "description": "Language cookie lifetime in seconds", "is_secret": False},
        {"key": "i18n.cookie_secure", "value": True, "value_type": "bool", "description": "Send language cookie only over HTTPS", "is_secret": False},
        {"key": "i18n.trusted_proxy_ips", "value": [], "value_type": "json", "description": "Proxy IPs/CIDRs trusted to supply country metadata", "is_secret": False},
        {"key": "i18n.country_header", "value": "CF-IPCountry", "value_type": "string", "description": "Trusted proxy country-code header", "is_secret": False},
        {"key": "batch.template_examples", "value": {}, "value_type": "json", "description": "Localized batch-template example overrides", "is_secret": False},
    ])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM sys_configs WHERE key LIKE 'i18n.%' OR key = 'batch.template_examples'"))
    op.drop_table("language_preference")
