from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models import (AdminUser, AiMatchEvidence, Base, LlmCallLog, Machine, MachinePartRelation,
                        Part, PartQueryLog, SysConfig)
from app.services.ai_matching import AiMatchingService, AiRateLimiter, OpenAICompatibleProvider, rules_intent
from app.services.cache import get_cache

engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def foreign_keys(connection, _record):
    connection.execute("PRAGMA foreign_keys=ON")


Session = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)


class NullCache:
    async def get(self, _key): return None
    async def set(self, _key, _value, ttl=None): return None
    @staticmethod
    def part_number_key(value): return value


def override_db():
    with Session() as db:
        yield db


@pytest.fixture(autouse=True)
def data():
    old_db, old_cache = app.dependency_overrides.get(get_db), app.dependency_overrides.get(get_cache)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_cache] = lambda: NullCache()
    with Session() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        admin = AdminUser(username="audit", password_hash=hash_password("password123"), role="operator", is_active=True)
        safe = Part(sku="SAFE-1", part_no="BRK-100", oem_no="OEM-BRK", brand="CAT", category="brake",
                    name_zh="制动片", name_en="Brake pad", name_vi="Má phanh", specs={}, price=Decimal("10"), stock=3, is_active=True)
        other = Part(sku="SAFE-2", part_no="BRK-101", oem_no=None, brand="CAT", category="brake",
                     name_zh="制动片副件", name_en="Brake pad alternate", name_vi=None, specs={}, price=Decimal("8"), stock=2, is_active=True)
        machine = Machine(machine_type="excavator", brand="CAT", model="320D", engine_model="C6.4")
        db.add_all([admin, safe, other, machine])
        db.flush()
        db.add_all([MachinePartRelation(machine_id=machine.id, part_id=safe.id, system="brake", priority=10),
                    MachinePartRelation(machine_id=machine.id, part_id=other.id, system="brake", priority=9)])
        db.commit()
        ids = {"safe": safe.id, "other": other.id}
    yield ids
    app.dependency_overrides.clear()
    if old_db: app.dependency_overrides[get_db] = old_db
    if old_cache: app.dependency_overrides[get_cache] = old_cache


def test_t1_rules_fallback_detects_zh_en_vi_and_fields():
    assert rules_intent("需要 CAT 320D 制动片 2件", "en", {"machine_brand": "CAT", "machine_model": "320D"}).lang == "zh"
    assert rules_intent("Need brake pad qty 3", "en", {}).part_category == "brake"
    vi = rules_intent("Cần má phanh số lượng 4", "en", {})
    assert vi.lang == "vi" and vi.quantity == 4 and vi.part_category == "brake"
    assert rules_intent("AB 12", "en", {}).part_no == "AB12"


@pytest.mark.asyncio
async def test_t1_provider_responses_and_chat_payload_and_parsing(monkeypatch):
    calls = []

    class Response:
        def __init__(self, body): self.body = body
        def raise_for_status(self): return None
        def json(self): return self.body

    class Client:
        def __init__(self, **_kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): return None
        async def post(self, url, headers, json):
            calls.append((url, headers, json))
            if url.endswith("/responses"):
                return Response({"output_text": '{"ok":true}', "usage": {"input_tokens": 2, "output_tokens": 1}})
            return Response({"choices": [{"message": {"content": "```json\n{\"ok\":true}\n```"}}],
                             "usage": {"prompt_tokens": 3, "completion_tokens": 1}})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
    responses = OpenAICompatibleProvider(base_url="https://provider/v1", api_key="secret", model="configured", api_mode="responses", timeout=1)
    parsed, usage = await responses.structured(purpose="test", system="s", user="u", schema=schema, safety_identifier="sid")
    assert parsed == {"ok": True} and usage["input_tokens"] == 2
    assert calls[0][2]["text"]["format"]["strict"] is True and calls[0][2]["safety_identifier"] == "sid"
    chat = OpenAICompatibleProvider(base_url="https://provider/v1", api_key="secret", model="configured", api_mode="chat_completions", timeout=1)
    parsed, _ = await chat.structured(purpose="test", system="s", user="u", schema=schema, safety_identifier="sid")
    assert parsed == {"ok": True} and calls[1][2]["response_format"]["json_schema"]["strict"] is True
    assert "secret" not in str(calls[0][2])


class InventingProvider:
    def __init__(self, valid_id): self.valid_id = valid_id; self.calls = 0
    async def structured(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return ({"intent": "find_part", "part_category": "brake", "machine_brand": "CAT",
                     "machine_model": "320D", "serial_no": None, "engine_model": None, "part_no": None,
                     "quantity": 1, "lang": "en"}, {"input_tokens": 10, "output_tokens": 5})
        return ({"ranked": [{"part_id": "invented-id", "score": 1, "reason": "invented"},
                            {"part_id": self.valid_id, "score": .99, "reason": "database evidence"}]},
                {"input_tokens": 20, "output_tokens": 8})


@pytest.mark.asyncio
async def test_t2_to_t7_merge_rejects_invented_ids_caps_safety_persists_logs_and_evidence(data):
    with Session() as db:
        provider = InventingProvider(data["safe"])
        result = await AiMatchingService(db, provider=provider).search(
            "Need CAT 320D brake pad", "en", {}, "session-stable", None,
        )
        assert "invented-id" not in {item.part.id for item in result.candidates}
        assert result.candidates[0].confidence <= .89
        assert result.candidates[0].match_status == "high"
        assert result.need_manual is True
        assert result.follow_up_questions
        assert result.provider == "llm"
        calls = list(db.scalars(select(LlmCallLog)))
        assert len(calls) == 2 and all(len(item.prompt_hash) == 64 for item in calls)
        assert all("Need CAT" not in (item.error_message or "") for item in calls)
        assert calls[0].input_tokens == 10 and calls[0].safety_identifier == calls[1].safety_identifier


def test_t5_get_post_query_logs_admin_permissions_and_evidence(data):
    client = TestClient(app)
    assert client.get("/api/v1/admin/query-logs").status_code == 401
    get_result = client.get("/api/v1/search", params={"type": "part_no", "q": "BRK-100"}, headers={"X-Session-Id": "s1"})
    assert get_result.status_code == 200
    post_result = client.post("/api/v1/search", json={"query": "BRK-100", "lang": "en"}, headers={"X-Session-Id": "s1"})
    assert post_result.status_code == 200 and post_result.json()["data"]["query_id"]
    with Session() as db:
        logs = list(db.scalars(select(PartQueryLog).order_by(PartQueryLog.created_at)))
        assert len(logs) == 2 and {row.query_type for row in logs} == {"part_no", "ai"}
        assert db.scalar(select(AiMatchEvidence).where(AiMatchEvidence.query_log_id == logs[-1].id)) is not None
    token = client.post("/api/v1/admin/auth/login", json={"username": "audit", "password": "password123"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    listing = client.get("/api/v1/admin/query-logs", params={"status": "high", "page_size": 10}, headers=headers)
    assert listing.status_code == 200
    detail = client.get(f"/api/v1/admin/query-logs/{post_result.json()['data']['query_id']}", headers=headers)
    assert detail.status_code == 200 and detail.json()["data"]["evidence"]


def test_t7_db_sliding_window_is_configurable_and_proxy_header_not_trusted(data):
    with Session() as db:
        db.add(SysConfig(key="ai.rate_limit_per_minute", value=2, value_type="int", is_secret=False))
        db.commit()
        limiter = AiRateLimiter(db)
        assert limiter.consume("198.51.100.9") is True
        assert limiter.consume("198.51.100.9") is True
        assert limiter.consume("198.51.100.9") is False
        db.rollback()
    client = TestClient(app)
    response = client.post("/api/v1/search", json={"query": "brake pad", "lang": "en"},
                           headers={"X-Forwarded-For": "203.0.113.55", "X-Session-Id": "proxy-test"})
    assert response.status_code == 200
    with Session() as db:
        log = db.scalar(select(PartQueryLog).where(PartQueryLog.session_id == "proxy-test"))
        assert log.client_ip != "203.0.113.55"
