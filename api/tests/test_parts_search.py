from __future__ import annotations

import time
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.models import (
    Base, Machine, MachinePartRelation, Part, PartAlias, PartCategory,
    PartCrossReference, PartImage,
)
from app.services.cache import get_cache


engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, _record):
    connection.execute("PRAGMA foreign_keys=ON")


TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)


class MemoryCache:
    def __init__(self):
        self.values = {}
        self.gets = 0
        self.sets = 0

    async def get(self, key):
        self.gets += 1
        return self.values.get(key)

    async def set(self, key, value, ttl=None):
        self.sets += 1
        self.values[key] = value

    @staticmethod
    def part_number_key(value):
        return "part:no:" + "".join(value.upper().split())


cache = MemoryCache()


def override_db():
    with TestingSession() as session:
        yield session


def override_cache():
    return cache


client = TestClient(app)


@pytest.fixture(autouse=True)
def catalogue():
    old_db = app.dependency_overrides.get(get_db)
    old_cache = app.dependency_overrides.get(get_cache)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_cache] = override_cache
    cache.values.clear()
    cache.gets = cache.sets = 0
    with TestingSession() as db:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name == "part_category":
                db.execute(table.delete().where(table.c.parent_id.is_not(None)))
            db.execute(table.delete())

        root = PartCategory(name="发动机", slug="engine", sort_order=1, is_active=True)
        db.add(root)
        db.flush()
        db.add(PartCategory(name="滤清器", slug="filters", parent_id=root.id, sort_order=1, is_active=True))
        primary = Part(
            sku="SKU-PRIMARY", part_no=" ab 12 ", oem_no=" oem 99 ", brand="Toyota",
            category="engine", name_zh="空气滤芯", name_en="Air Filter", name_vi="Lọc gió",
            specs={"length_mm": 210}, price=Decimal("88.00"), stock=20, is_active=True,
        )
        replacement = Part(
            sku="SKU-ALT", part_no="ALT-12", oem_no="ALT-OEM", brand="AfterCo",
            category="engine", name_zh="替代空气滤芯", name_en="Replacement Air Filter", name_vi=None,
            specs={}, price=Decimal("50.00"), stock=5, is_active=True,
        )
        inactive = Part(
            sku="SKU-OFF", part_no="OFF-1", oem_no="OFF-OEM", brand="Toyota",
            category="engine", name_zh="停用滤芯", name_en="Inactive Filter", name_vi=None,
            specs={}, price=None, stock=0, is_active=False,
        )
        db.add_all([primary, replacement, inactive])
        db.flush()
        machine = Machine(machine_type="forklift", brand="Toyota", model="8FD30", series="8",
                          year=2024, region="CN", engine_model="1DZ-II")
        db.add(machine)
        db.flush()
        db.add_all([
            MachinePartRelation(machine_id=machine.id, part_id=primary.id, system="engine",
                                position="intake", serial_from="1000", priority=10),
            MachinePartRelation(machine_id=machine.id, part_id=replacement.id, system="engine", priority=8),
            MachinePartRelation(machine_id=machine.id, part_id=inactive.id, system="engine", priority=20),
            PartCrossReference(source_part_id=replacement.id, target_part_id=primary.id,
                               relation_type="aftermarket", reliability=Decimal("0.9200")),
            PartAlias(part_id=primary.id, alias="空滤", language="zh", status="active"),
            PartAlias(part_id=inactive.id, alias="停用别名", language="zh", status="active"),
            PartImage(part_id=primary.id, file_id="file-1", url="https://assets.test/filter.jpg", sort_order=0),
        ])
        db.commit()
        ids = {"primary": primary.id, "replacement": replacement.id, "inactive": inactive.id}
    yield ids
    if old_db is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = old_db
    if old_cache is None:
        app.dependency_overrides.pop(get_cache, None)
    else:
        app.dependency_overrides[get_cache] = old_cache


def assert_envelope(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"code", "message", "data"}
    assert body["code"] == 0
    return body["data"]


def test_t1_exact_part_number_normalization_images_fitments_and_cache(catalogue):
    first = assert_envelope(client.get("/api/v1/search", params={"type": "part_no", "q": " aB 12 "}))
    assert first["query_type"] == "part_no"
    assert first["match_status"] == "exact"
    assert len(first["candidates"]) == 1
    candidate = first["candidates"][0]
    assert candidate["part"]["id"] == catalogue["primary"]
    assert candidate["part"]["images"][0]["url"].endswith("filter.jpg")
    assert candidate["fitments"][0]["model"] == "8FD30"
    assert candidate["confidence"] == 1.0
    assert cache.sets == 1
    second = assert_envelope(client.get("/api/v1/search?type=part_no&q=AB12"))
    assert second == first
    assert cache.gets == 2


def test_t1_redis_failure_degrades_to_database(catalogue, monkeypatch):
    async def fail(*_args, **_kwargs):
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(cache, "get", fail)
    monkeypatch.setattr(cache, "set", fail)
    result = assert_envelope(client.get("/api/v1/search?type=part_no&q=AB12"))
    assert result["candidates"][0]["part"]["id"] == catalogue["primary"]


def test_t1_cache_never_resurrects_a_deactivated_part(catalogue):
    assert assert_envelope(client.get("/api/v1/search?type=part_no&q=AB12"))["candidates"]
    with TestingSession.begin() as db:
        db.get(Part, catalogue["primary"]).is_active = False
    refreshed = assert_envelope(client.get("/api/v1/search?type=part_no&q=AB12"))
    assert refreshed["match_status"] == "not_found"
    assert refreshed["candidates"] == []


def test_t2_oem_includes_original_and_bidirectional_replacement(catalogue):
    result = assert_envelope(client.get("/api/v1/search?type=oem&q=oem%2099"))
    by_id = {item["part"]["id"]: item for item in result["candidates"]}
    assert set(by_id) == {catalogue["primary"], catalogue["replacement"]}
    assert by_id[catalogue["primary"]]["relation_type"] == "OEM"
    assert by_id[catalogue["replacement"]]["relation_type"] == "aftermarket"
    assert by_id[catalogue["replacement"]]["reliability"] == 0.92


def test_t3_machine_groups_active_parts_and_falls_back_to_categories(catalogue):
    result = assert_envelope(client.get("/api/v1/search?type=machine&q=toyota&model=8fd30"))
    assert result["query_type"] == "machine"
    assert result["match_status"] == "exact"
    assert set(result["groups"]["engine"]) == {catalogue["primary"], catalogue["replacement"]}
    assert catalogue["inactive"] not in {c["part"]["id"] for c in result["candidates"]}
    missing = assert_envelope(client.get("/api/v1/search?type=machine&q=missing&model=nope"))
    assert missing["match_status"] == "not_found"
    assert missing["category_navigation"][0]["slug"] == "engine"


def test_t4_engine_returns_engine_maintenance_parts_and_serial_flag(catalogue):
    result = assert_envelope(client.get("/api/v1/search?type=engine&q=1dz-II"))
    assert result["query_type"] == "engine"
    assert {c["part"]["id"] for c in result["candidates"]} == {catalogue["primary"], catalogue["replacement"]}
    by_id = {c["part"]["id"]: c for c in result["candidates"]}
    assert by_id[catalogue["primary"]]["requires_serial_confirmation"] is True


def test_t5_multilingual_names_aliases_relevance_and_inactive_filter(catalogue):
    alias = assert_envelope(client.get("/api/v1/search?type=text&q=空滤&lang=zh"))
    assert alias["candidates"][0]["part"]["id"] == catalogue["primary"]
    assert alias["candidates"][0]["confidence"] == 1.0
    english = assert_envelope(client.get("/api/v1/search?type=text&q=Air%20Filter&lang=en"))
    assert english["candidates"][0]["part"]["id"] == catalogue["primary"]
    inactive = assert_envelope(client.get("/api/v1/search?type=text&q=停用别名&lang=zh"))
    assert inactive["match_status"] == "not_found"


def test_t6_comprehensive_detection_and_clear_m6_fallback(catalogue):
    assert assert_envelope(client.post("/api/v1/search", json={"query": "AB 12"}))["query_type"] == "part_no"
    assert assert_envelope(client.post("/api/v1/search", json={"query": "OEM99"}))["query_type"] == "oem"
    assert assert_envelope(client.post("/api/v1/search", json={"query": "8FD30"}))["query_type"] == "machine"
    assert assert_envelope(client.post("/api/v1/search", json={"query": "1DZ-II"}))["query_type"] == "engine"
    natural = assert_envelope(client.post("/api/v1/search", json={"query": "完全未知描述", "lang": "zh", "context": {}}))
    assert natural["query_type"] == "natural"
    assert natural["match_status"] == "not_found"
    assert any("M6" in suggestion for suggestion in natural["suggestions"])
    short = assert_envelope(client.post("/api/v1/search", json={"query": "泵", "lang": "zh"}))
    assert short["match_status"] == "insufficient"


def test_t7_detail_is_complete_bidirectional_and_hides_inactive(catalogue):
    detail = assert_envelope(client.get(f"/api/v1/parts/{catalogue['primary']}"))
    assert detail["specs"] == {"length_mm": 210}
    assert detail["images"][0]["file_id"] == "file-1"
    assert detail["machines"][0]["model"] == "8FD30"
    assert detail["engines"] == ["1DZ-II"]
    assert detail["alternatives"][0]["part"]["id"] == catalogue["replacement"]
    assert client.get(f"/api/v1/parts/{catalogue['inactive']}").status_code == 404


def test_t8_categories_and_hot_lists_are_renderable_and_active_only(catalogue):
    categories = assert_envelope(client.get("/api/v1/categories"))
    assert categories[0]["children"][0]["slug"] == "filters"
    machines = assert_envelope(client.get("/api/v1/machines/hot"))
    assert machines[0]["model"] == "8FD30" and machines[0]["part_count"] == 2
    parts = assert_envelope(client.get("/api/v1/parts/hot"))
    assert catalogue["inactive"] not in {part["id"] for part in parts}


def test_t9_exact_query_uses_index_and_repeatable_benchmark_under_three_seconds(catalogue):
    with engine.connect() as connection:
        plan = connection.execute(text(
            "EXPLAIN QUERY PLAN SELECT * FROM part WHERE part_no = 'AB12' AND is_active = 1"
        )).all()
        assert any("uq_part_part_no" in str(row) for row in plan), plan
        indexes = {row[1] for row in connection.execute(text("PRAGMA index_list('machine')"))}
        assert "ix_machine_brand_model" in indexes
        start = time.perf_counter()
        for _ in range(500):
            connection.execute(text("SELECT id FROM part WHERE part_no = 'AB12' AND is_active = 1")).all()
        assert time.perf_counter() - start < 3

    migration = (Path(__file__).parents[1] / "migrations/versions/55d72af1c901_search_indexes.py").read_text()
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in migration
    assert "gin_trgm_ops" in migration
