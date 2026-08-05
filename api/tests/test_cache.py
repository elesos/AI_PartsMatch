import pytest

from app.services.cache import CacheService


class MemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key): return self.values.get(key)
    async def set(self, key, value, ex=None): self.values[key] = value
    async def delete(self, key): return int(self.values.pop(key, None) is not None)
    async def ping(self): return True


@pytest.mark.asyncio
async def test_cache_round_trip_and_key_convention() -> None:
    cache = CacheService(MemoryRedis())
    await cache.set("sample", {"value": 1}, ttl=30)
    assert await cache.get("sample") == {"value": 1}
    assert await cache.delete("sample") is True
    assert CacheService.part_number_key(" ab 12 ") == "part:no:AB12"
