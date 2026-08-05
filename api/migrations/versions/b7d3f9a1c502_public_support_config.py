"""public frontend and support configuration

Revision ID: b7d3f9a1c502
Revises: 21c7d94e5a30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d3f9a1c502"
down_revision: Union[str, None] = "21c7d94e5a30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    configs = sa.table("sys_configs", sa.column("key", sa.String), sa.column("value", sa.JSON),
                       sa.column("value_type", sa.String), sa.column("description", sa.String),
                       sa.column("is_secret", sa.Boolean))
    op.bulk_insert(configs, [
        {"key": "frontend.api_base_url", "value": "https://match-api.elesos.cc", "value_type": "string", "description": "Public API origin used by the customer frontend", "is_secret": False},
        {"key": "support.whatsapp_url", "value": "", "value_type": "string", "description": "Public HTTPS WhatsApp contact link (blank disables)", "is_secret": False},
        {"key": "support.zalo_url", "value": "", "value_type": "string", "description": "Public HTTPS Zalo contact link (blank disables)", "is_secret": False},
        {"key": "support.telegram_url", "value": "", "value_type": "string", "description": "Public HTTPS Telegram contact link (blank disables)", "is_secret": False},
        {"key": "support.wechat_label", "value": "", "value_type": "string", "description": "Public WeChat contact label (blank disables)", "is_secret": False},
    ])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM sys_configs WHERE key IN ('frontend.api_base_url', 'support.whatsapp_url', 'support.zalo_url', 'support.telegram_url', 'support.wechat_label')"))
