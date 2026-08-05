from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.models import Base, CartItem, InquiryOrder, InquiryOrderItem, Machine, MachinePartRelation, Part, PartImage, PartQueryLog, SysConfig


engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def foreign_keys(connection, _record):
    connection.execute("PRAGMA foreign_keys=ON")


TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)
client = TestClient(app)
SESSION_A = {"X-Session-Id": "anonymous-session-a"}
SESSION_B = {"X-Session-Id": "anonymous-session-b"}


def override_db():
    with TestingSession() as session:
        yield session


def data(response, status=200):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "data"}
    assert body["code"] == 0
    return body["data"]


@pytest.fixture(autouse=True)
def catalogue():
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_db
    with TestingSession.begin() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        normal = Part(sku="CART-1", part_no="C-1", oem_no="OEM-C1", brand="Acme", category="filters",
                      name_zh="滤芯", name_en="Filter", specs={}, price=Decimal("12.50"), stock=10, is_active=True)
        safety = Part(sku="CART-2", part_no="C-2", brand="Acme", category="engine",
                      name_zh="发动机件", specs={}, price=Decimal("20.00"), stock=10, is_active=True)
        inactive = Part(sku="CART-3", part_no="C-3", brand="Acme", category="filters",
                        name_zh="停用件", specs={}, price=Decimal("1.00"), stock=0, is_active=False)
        db.add_all([normal, safety, inactive])
        db.flush()
        machine = Machine(machine_type="forklift", brand="Toyota", model="8FD30")
        db.add(machine)
        db.flush()
        db.add_all([
            PartImage(part_id=normal.id, file_id="cart-file", url="https://assets.test/cart.jpg", sort_order=0),
            MachinePartRelation(machine_id=machine.id, part_id=normal.id, system="maintenance", priority=1),
        ])
        ids = {"normal": normal.id, "safety": safety.id, "inactive": inactive.id}
    yield ids
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def test_t1_crud_requires_valid_identity_and_isolates_sessions(catalogue):
    missing = client.get("/api/v1/cart")
    assert missing.status_code == 400 and missing.json()["code"] == 40020
    assert client.get("/api/v1/cart", headers={"X-Session-Id": "bad"}).status_code == 400
    created = data(client.post("/api/v1/cart/items", headers=SESSION_A,
                               json={"part_id": catalogue["normal"], "quantity": 2}), 201)
    assert created["quantity"] == 2
    assert data(client.get("/api/v1/cart", headers=SESSION_B))["items"] == []
    updated = data(client.put(f"/api/v1/cart/items/{created['id']}", headers=SESSION_A, json={"quantity": 4}))
    assert updated["quantity"] == 4
    assert client.put(f"/api/v1/cart/items/{created['id']}", headers=SESSION_B, json={"quantity": 1}).status_code == 404
    assert client.post("/api/v1/cart/items", headers=SESSION_A,
                       json={"part_id": catalogue["inactive"], "quantity": 1}).status_code == 404
    assert client.delete(f"/api/v1/cart/items/{created['id']}", headers=SESSION_A).status_code == 204
    assert data(client.get("/api/v1/cart", headers=SESSION_A))["items"] == []


def test_t2_native_upsert_merges_quantity_and_touches_timestamp(catalogue):
    first = data(client.post("/api/v1/cart/items", headers=SESSION_A,
                             json={"part_id": catalogue["normal"], "quantity": 2}), 201)
    with TestingSession() as db:
        before = db.get(CartItem, first["id"]).updated_at
    second = data(client.post("/api/v1/cart/items", headers=SESSION_A,
                              json={"part_id": catalogue["normal"], "quantity": 3}), 201)
    assert second["id"] == first["id"] and second["quantity"] == 5
    with TestingSession() as db:
        rows = db.scalars(select(CartItem)).all()
        assert len(rows) == 1 and rows[0].updated_at >= before


def test_t3_confidence_status_safety_category_and_sys_config(catalogue):
    low = data(client.post("/api/v1/cart/items", headers=SESSION_A, json={
        "part_id": catalogue["normal"], "confidence": 0.69, "match_status": "exact", "source": "search",
    }), 201)
    assert low["need_confirm"] is True
    safety = data(client.post("/api/v1/cart/items", headers=SESSION_A, json={
        "part_id": catalogue["safety"], "confidence": 1, "match_status": "exact",
    }), 201)
    assert safety["need_confirm"] is True
    with TestingSession.begin() as db:
        db.add(SysConfig(key="cart.confirm_confidence_threshold", value=0.9))
    configured = data(client.post("/api/v1/cart/items", headers=SESSION_B, json={
        "part_id": catalogue["normal"], "confidence": 0.85, "match_status": "exact", "source": "search",
    }), 201)
    assert configured["need_confirm"] is True


def test_t4_summary_contains_renderable_fields_and_totals(catalogue):
    data(client.post("/api/v1/cart/items", headers=SESSION_A,
                     json={"part_id": catalogue["normal"], "quantity": 3}), 201)
    summary = data(client.get("/api/v1/cart/summary", headers=SESSION_A))
    assert summary == summary | {"total_items": 1, "total_quantity": 3, "total_amount": 37.5, "need_confirm_count": 0}
    item = summary["items"][0]
    assert item["image"]["url"].endswith("cart.jpg")
    assert item["name"] == "滤芯" and item["part_no"] == "C-1" and item["oem"] == "OEM-C1"
    assert item["fitments"][0]["model"] == "8FD30" and item["unit_price"] == 12.5 and item["subtotal"] == 37.5


def test_t5_submit_freezes_item_and_price_snapshot(catalogue):
    data(client.post("/api/v1/cart/items", headers=SESSION_A,
                     json={"part_id": catalogue["normal"], "quantity": 2}), 201)
    result = data(client.post("/api/v1/cart/submit", headers=SESSION_A, json={
        "contact_name": "Buyer", "country": "Vietnam", "contact_method": "+8613800000000",
        "communication_tool": "zalo", "note": "quote",
    }), 201)
    assert result["order_no"].startswith("INQ-") and result["total_amount"] == 25
    with TestingSession.begin() as db:
        db.get(Part, catalogue["normal"]).price = Decimal("999.00")
    with TestingSession() as db:
        order = db.get(InquiryOrder, result["order_id"])
        snapshot = db.scalar(select(InquiryOrderItem).where(InquiryOrderItem.order_id == order.id))
        assert order.country == "Vietnam" and order.communication_tool == "zalo"
        assert order.total_amount == Decimal("25.00")
        assert snapshot.unit_price == Decimal("12.50") and snapshot.snapshot["name"] == "滤芯"


def test_t6_from_match_optional_log_and_owned_query_validation(catalogue):
    without_log = data(client.post("/api/v1/cart/items/from-match", headers=SESSION_A, json={
        "part_id": catalogue["normal"], "quantity": 1, "match_status": "exact", "confidence": 0.95, "source": "image",
    }), 201)
    assert without_log["query_id"] is None and without_log["source"] == "image"
    with TestingSession.begin() as db:
        own = PartQueryLog(session_id=SESSION_A["X-Session-Id"], query_type="image", request_data={}, result_count=1)
        foreign = PartQueryLog(session_id=SESSION_B["X-Session-Id"], query_type="text", request_data={}, result_count=1)
        db.add_all([own, foreign])
        db.flush()
        own_id, foreign_id = own.id, foreign.id
    linked = data(client.post("/api/v1/cart/items/from-match", headers=SESSION_A, json={
        "part_id": catalogue["normal"], "quantity": 1, "query_id": own_id,
        "match_status": "multiple", "confidence": 0.8, "source": "manual",
    }), 201)
    assert linked["query_id"] == own_id and linked["need_confirm"] is True
    assert client.post("/api/v1/cart/items/from-match", headers=SESSION_A, json={
        "part_id": catalogue["normal"], "query_id": foreign_id, "match_status": "exact", "confidence": 1,
    }).status_code == 403
    assert client.post("/api/v1/cart/items/from-match", headers=SESSION_A, json={
        "part_id": catalogue["normal"], "match_status": "exact", "confidence": 1, "source": "untrusted",
    }).status_code == 422


def test_inquiry_submit_accepts_telegram_and_country_is_nullable(catalogue):
    data(client.post("/api/v1/cart/items", headers=SESSION_A,
                     json={"part_id": catalogue["normal"], "quantity": 1}), 201)
    result = data(client.post("/api/v1/cart/submit", headers=SESSION_A, json={
        "contact_name": "Buyer", "contact_method": "@parts_buyer", "communication_tool": "telegram",
    }), 201)
    with TestingSession() as db:
        order = db.get(InquiryOrder, result["order_id"])
        assert order.country is None and order.communication_tool == "telegram"


def test_country_migration_follows_i18n_head_and_is_reversible():
    migration = (Path(__file__).parents[1] / "migrations/versions/21c7d94e5a30_inquiry_order_country.py").read_text()
    assert 'down_revision: Union[str, None] = "f19b2c4d8e60"' in migration
    assert 'op.add_column("inquiry_order"' in migration
    assert 'op.drop_column("inquiry_order", "country")' in migration
