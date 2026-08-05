"""AI matching, query audit and rate limiting

Revision ID: e7a6c4b2d901
Revises: d4e5f6a7b8c9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7a6c4b2d901"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for name, column in (
        ("user_id", sa.Column("user_id", sa.String(36))),
        ("client_ip", sa.Column("client_ip", sa.String(64))),
        ("confidence", sa.Column("confidence", sa.Numeric(5, 4))),
        ("match_status", sa.Column("match_status", sa.String(30))),
        ("need_manual", sa.Column("need_manual", sa.Boolean(), nullable=False, server_default=sa.false())),
    ):
        op.add_column("part_query_log", column)
        if name != "confidence":
            op.create_index(op.f(f"ix_part_query_log_{name}"), "part_query_log", [name])

    op.create_table(
        "llm_call_log",
        sa.Column("query_log_id", sa.String(36)), sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("api_mode", sa.String(30), nullable=False), sa.Column("model", sa.String(100)),
        sa.Column("prompt_hash", sa.String(64), nullable=False), sa.Column("safety_identifier", sa.String(64), nullable=False),
        sa.Column("input_tokens", sa.Integer()), sa.Column("output_tokens", sa.Integer()),
        sa.Column("duration_ms", sa.Integer(), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("error_type", sa.String(50)), sa.Column("error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.ForeignKeyConstraint(["query_log_id"], ["part_query_log.id"], ondelete="SET NULL"),
    )
    for name in ("query_log_id", "provider", "prompt_hash", "safety_identifier", "status", "error_type", "created_at"):
        op.create_index(op.f(f"ix_llm_call_log_{name}"), "llm_call_log", [name])

    op.create_table(
        "ai_rate_limit_event",
        sa.Column("client_key", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.String(36), primary_key=True),
    )
    op.create_index(op.f("ix_ai_rate_limit_event_client_key"), "ai_rate_limit_event", ["client_key"])
    op.create_index(op.f("ix_ai_rate_limit_event_created_at"), "ai_rate_limit_event", ["created_at"])
    op.create_index("ix_ai_rate_limit_client_window", "ai_rate_limit_event", ["client_key", "created_at"])

    configs = sa.table("sys_configs", sa.column("key", sa.String), sa.column("value", sa.JSON),
                       sa.column("value_type", sa.String), sa.column("description", sa.String), sa.column("is_secret", sa.Boolean))
    op.bulk_insert(configs, [
        {"key": "ai.api_key", "value": "", "value_type": "string", "description": "OpenAI-compatible API key", "is_secret": True},
        {"key": "ai.base_url", "value": "https://api.openai.com/v1", "value_type": "string", "description": "OpenAI-compatible API base URL", "is_secret": False},
        {"key": "ai.api_mode", "value": "responses", "value_type": "string", "description": "responses or chat_completions", "is_secret": False},
        {"key": "ai.model", "value": "", "value_type": "string", "description": "Configured model name; intentionally no hard-coded default", "is_secret": False},
        {"key": "ai.timeout_seconds", "value": 20, "value_type": "int", "description": "LLM request timeout", "is_secret": False},
        {"key": "ai.top_n", "value": 10, "value_type": "int", "description": "Maximum merged candidates", "is_secret": False},
        {"key": "ai.exact_threshold", "value": 0.9, "value_type": "float", "description": "Exact confidence threshold", "is_secret": False},
        {"key": "ai.high_threshold", "value": 0.7, "value_type": "float", "description": "High confidence threshold", "is_secret": False},
        {"key": "ai.low_threshold", "value": 0.4, "value_type": "float", "description": "Manual/not-found threshold", "is_secret": False},
        {"key": "ai.close_candidate_gap", "value": 0.05, "value_type": "float", "description": "Ambiguous candidate score gap", "is_secret": False},
        {"key": "ai.rate_limit_per_minute", "value": 20, "value_type": "int", "description": "AI searches per client IP per minute", "is_secret": False},
        {"key": "ai.trusted_proxy_ips", "value": [], "value_type": "json", "description": "Direct proxy peer IPs allowed to supply X-Forwarded-For", "is_secret": False},
        {"key": "ai.safety_salt", "value": "partsmatch-safety-v1", "value_type": "string", "description": "Salt for privacy-preserving stable safety identifier", "is_secret": True},
    ])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM sys_configs WHERE key LIKE 'ai.%'"))
    op.drop_index("ix_ai_rate_limit_client_window", table_name="ai_rate_limit_event")
    op.drop_table("ai_rate_limit_event")
    op.drop_table("llm_call_log")
    for name in ("need_manual", "match_status", "client_ip", "user_id"):
        op.drop_index(op.f(f"ix_part_query_log_{name}"), table_name="part_query_log")
    for name in ("need_manual", "match_status", "confidence", "client_ip", "user_id"):
        op.drop_column("part_query_log", name)
