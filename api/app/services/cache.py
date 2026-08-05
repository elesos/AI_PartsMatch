import json
from typing import Any

from redis.asyncio import Redis
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.services.config_service import ConfigService


class CacheService:
    def __init__(self, client: Redis | None = None) -> None:
        self.client = client or Redis.from_url(get_settings().redis_url, decode_responses=True)

    async def get(self, key: str) -> Any | None:
        value = await self.client.get(key)
        return json.loads(value) if value is not None else None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self.client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)

    async def delete(self, key: str) -> bool:
        return bool(await self.client.delete(key))

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    @staticmethod
    def part_number_key(part_no: str) -> str:
        from app.services.catalog_validation import normalize_part_number

        normalized = normalize_part_number(part_no)
        return f"part:no:{normalized}"


def get_cache(db: Session = Depends(get_db)) -> CacheService:
    redis_url = ConfigService(db).get("redis.url", get_settings().redis_url)
    return CacheService(Redis.from_url(redis_url, decode_responses=True))
