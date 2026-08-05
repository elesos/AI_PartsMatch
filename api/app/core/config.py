from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _bootstrap_value(name: str, default: str, *, secret_name: str | None = None) -> str:
    """Read an immutable bootstrap value from a Docker secret or process input."""
    secret_path = Path("/run/secrets") / (secret_name or name.lower())
    if secret_path.is_file():
        return secret_path.read_text(encoding="utf-8").strip()
    return os.environ.get(name, default)


@dataclass(frozen=True, slots=True)
class BootstrapSettings:
    app_name: str = "PartsMatch API"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite+pysqlite:///./partsmatch.db"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "partsmatch"
    s3_secret_key: str = "partsmatch-local-only"
    s3_bucket: str = "partsmatch"
    s3_public_url: str = "http://localhost:9000/partsmatch"
    jwt_secret: str = "local-development-secret-change-me"


@lru_cache
def get_settings() -> BootstrapSettings:
    defaults = BootstrapSettings()
    return BootstrapSettings(
        database_url=_bootstrap_value("DATABASE_URL", defaults.database_url, secret_name="database_url"),
        redis_url=_bootstrap_value("REDIS_URL", defaults.redis_url, secret_name="redis_url"),
        s3_endpoint_url=_bootstrap_value("S3_ENDPOINT_URL", defaults.s3_endpoint_url),
        s3_access_key=_bootstrap_value("S3_ACCESS_KEY", defaults.s3_access_key, secret_name="s3_access_key"),
        s3_secret_key=_bootstrap_value("S3_SECRET_KEY", defaults.s3_secret_key, secret_name="s3_secret_key"),
        s3_bucket=_bootstrap_value("S3_BUCKET", defaults.s3_bucket),
        s3_public_url=_bootstrap_value("S3_PUBLIC_URL", defaults.s3_public_url),
        jwt_secret=_bootstrap_value("JWT_SECRET", defaults.jwt_secret, secret_name="jwt_secret"),
    )
