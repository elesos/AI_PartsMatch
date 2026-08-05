from typing import Any

from sqlalchemy.orm import Session

from app.models import SysConfig


class ConfigService:
    """Database-backed settings that take effect without restarting the API."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, key: str, default: Any = None) -> Any:
        config = self.db.get(SysConfig, key)
        return config.value if config else default

    def list(self) -> list[SysConfig]:
        return list(self.db.query(SysConfig).order_by(SysConfig.key).all())

    def set(self, key: str, value: Any, *, description: str | None = None, is_secret: bool = False) -> SysConfig:
        config = self.db.get(SysConfig, key)
        if config is None:
            config = SysConfig(key=key, value=value, description=description, is_secret=is_secret)
            self.db.add(config)
        else:
            config.value = value
            config.description = description if description is not None else config.description
            config.is_secret = is_secret
        self.db.commit()
        self.db.refresh(config)
        return config
