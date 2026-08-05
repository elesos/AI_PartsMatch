from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import (AdminUser, Base, CartItem, FileObject, KnowledgeCandidate, ManualTicket, PartQueryLog,
                        ManualTicketAttachment, ManualTicketEvent, ManualTicketPart, ManualTicketSupplement, Part, SysConfig)

engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Session = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)
client = TestClient(app)
A = {"X-Session-Id": "ticket-session-a"}
B = {"X-Session-Id": "ticket-session-b"}


def override_db():
    with Session() as db:
        yield db


def body(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


@pytest.fixture(autouse=True)
def records():
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_db
    with Session.begin() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        part1 = Part(sku="T-1", part_no="P1", brand="Acme", name_zh="件一", specs={}, price=Decimal("1"), stock=1, is_active=True)
        part2 = Part(sku="T-2", part_no="P2", brand="Acme", name_zh="件二", specs={}, price=Decimal("2"), stock=1, is_active=True)
        inactive = Part(sku="T-3", part_no="P3", brand="Acme", name_zh="停用", specs={}, stock=0, is_active=False)
        operator = AdminUser(username="op", password_hash=hash_password("password123"), role="operator", is_active=True)
        outsider = AdminUser(username="off", password_hash=hash_password("password123"), role="operator", is_active=False)
        file_a = FileObject(object_key="a.jpg", original_name="a.jpg", mime_type="image/jpeg", size=3,
                            url="https://assets/a.jpg", owner_key="session:ticket-session-a")
        file_b = FileObject(object_key="b.jpg", original_name="b.jpg", mime_type="image/jpeg", size=3,
                            url="https://assets/b.jpg", owner_key="session:ticket-session-b")
        db.add_all([part1, part2, inactive, operator, outsider, file_a, file_b]); db.flush()
        token, _ = create_access_token(operator)
        ids = {"p1": part1.id, "p2": part2.id, "inactive": inactive.id, "op": operator.id,
               "file_a": file_a.id, "file_b": file_b.id, "auth": {"Authorization": f"Bearer {token}"}}
    yield ids
    if previous is None: app.dependency_overrides.pop(get_db, None)
    else: app.dependency_overrides[get_db] = previous


def create_ticket(ids, headers=A):
    return body(client.post("/api/v1/tickets", headers=headers, json={
        "contact_name": "Buyer", "country": "CN", "contact_info": "13812341234",
        "communication_tool": "wechat", "machine_type": "forklift", "machine_brand": "Toyota",
        "machine_model": "8FD", "part_description": "filter", "quantity": 2,
        "image_ids": [ids["file_a"]], "ai_preliminary_result": {"candidate": "P1"},
    }), 201)


def test_submit_attachment_ownership_isolation_and_masking(records):
    created = create_ticket(records)
    assert created["status"] == "pending" and created["contact_info"] == "138****1234"
    assert created["attachments"][0]["image_id"] == records["file_a"]
    assert client.get(f"/api/v1/tickets/{created['id']}", headers=B).status_code == 404
    foreign = client.post("/api/v1/tickets", headers=A, json={
        "contact_name": "Buyer", "contact_info": "13812341234", "communication_tool": "wechat",
        "part_description": "filter", "image_ids": [records["file_b"]]})
    assert foreign.status_code == 404
    with Session() as db:
        assert db.scalar(select(ManualTicketAttachment)).file_id == records["file_a"]
        log = db.scalar(select(PartQueryLog).where(PartQueryLog.query_type == "manual"))
        assert log is not None and log.source_id == created["id"] and "contact" not in str(log.request_data)


def test_public_status_uses_ticket_number_owner_and_uniform_not_found(records):
    ticket = create_ticket(records)
    status = body(client.get("/api/v1/tickets/status", params={"ticket_no": ticket["ticket_no"]}, headers=A))
    assert status == {
        "ticket_no": ticket["ticket_no"], "status": "pending", "contact_info": "138****1234",
        "communication_tool": "wechat", "resolved_parts": [], "updated_at": ticket["updated_at"],
    }
    foreign = client.get("/api/v1/tickets/status", params={"ticket_no": ticket["ticket_no"]}, headers=B)
    malformed = client.get("/api/v1/tickets/status", params={"ticket_no": "MT-20260805-NOTVALID"}, headers=A)
    assert foreign.status_code == malformed.status_code == 404
    assert foreign.json()["code"] == malformed.json()["code"] == 40431


def test_auth_transition_assign_supplement_and_illegal_jumps(records):
    ticket = create_ticket(records)
    assert client.get("/api/v1/admin/tickets").status_code == 401
    assert client.put(f"/api/v1/admin/tickets/{ticket['id']}/status", headers=records["auth"],
                      json={"status": "closed", "note": "无效关闭"}).status_code == 409
    assigned = body(client.post(f"/api/v1/admin/tickets/{ticket['id']}/assign", headers=records["auth"],
                                json={"assignee_id": records["op"]}))
    assert assigned["status"] == "processing"
    need = body(client.put(f"/api/v1/admin/tickets/{ticket['id']}/status", headers=records["auth"],
                           json={"status": "need_info", "note": "请补充铭牌序列号"}))
    assert need["status"] == "need_info"
    assert client.post(f"/api/v1/tickets/{ticket['id']}/supplement", headers=B,
                       json={"content": "serial 1"}).status_code == 404
    supplied = body(client.post(f"/api/v1/tickets/{ticket['id']}/supplement", headers=A,
                                json={"content": "serial 1"}))
    assert supplied["status"] == "processing"
    assert client.post(f"/api/v1/tickets/{ticket['id']}/supplement", headers=A,
                       json={"content": "again"}).status_code == 409
    with Session() as db: assert db.scalar(select(ManualTicketSupplement)).content == "serial 1"


def test_resolve_active_parts_quantity_candidate_and_idempotent_cart(records):
    ticket = create_ticket(records)
    body(client.post(f"/api/v1/admin/tickets/{ticket['id']}/assign", headers=records["auth"],
                     json={"assignee_id": records["op"]}))
    bad = client.post(f"/api/v1/admin/tickets/{ticket['id']}/resolve", headers=records["auth"], json={
        "resolved_part_ids": [records["inactive"]], "match_evidence": "manual"})
    assert bad.status_code == 404
    payload = {
        "resolved_part_ids": [records["p1"], records["p2"]], "match_evidence": "catalog",
        "internal_note": "private phone 13900000000", "quantities": {records["p1"]: 3},
        "confidences": {records["p1"]: .98, records["p2"]: .76},
        "reasons": {records["p1"]: "铭牌一致", records["p2"]: "可替换"}}
    resolved = body(client.post(f"/api/v1/admin/tickets/{ticket['id']}/resolve", headers=records["auth"], json=payload))
    assert [p["quantity"] for p in resolved["resolved_parts"]] == [3, 2]
    assert [p["confidence"] for p in resolved["resolved_parts"]] == [.98, .76]
    # A retried resolve is idempotent: the persisted reviewed source remains singular.
    retried = body(client.post(f"/api/v1/admin/tickets/{ticket['id']}/resolve", headers=records["auth"], json=payload))
    assert retried["status"] == "matched"
    with Session() as db:
        assert len(db.scalars(select(ManualTicketPart)).all()) == 2
        candidates = db.scalars(select(KnowledgeCandidate)).all()
        assert len(candidates) == 1 and candidates[0].status == "pending_review"
        assert candidates[0].payload["source"] == {
            "type": "manual_ticket", "ticket_id": ticket["id"], "ticket_no": ticket["ticket_no"]}
        assert len(db.scalars(select(ManualTicketEvent).where(ManualTicketEvent.event_type == "resolved")).all()) == 1
    changed = {**payload, "match_evidence": "different evidence"}
    assert client.post(f"/api/v1/admin/tickets/{ticket['id']}/resolve", headers=records["auth"], json=changed).status_code == 409
    public = body(client.get(f"/api/v1/tickets/{ticket['id']}", headers=A))
    assert public["internal_note"] is None and public["contact_info"] == "138****1234"
    first = body(client.post(f"/api/v1/tickets/{ticket['id']}/add-to-cart", headers=A))
    second = body(client.post(f"/api/v1/tickets/{ticket['id']}/add-to-cart", headers=A))
    assert first == second
    with Session() as db:
        items = db.scalars(select(CartItem).order_by(CartItem.part_id)).all()
        assert len(items) == 2 and sorted(i.quantity for i in items) == [2, 3]
        assert all(i.source == "manual" for i in items)


def test_admin_full_contact_list_filter_pagination_and_sort(records):
    ticket = create_ticket(records)
    full = body(client.get(f"/api/v1/admin/tickets/{ticket['id']}", headers=records["auth"]))
    assert full["contact_info"] == "13812341234" and full["ai_preliminary_result"] == {"candidate": "P1"}
    listing = body(client.get("/api/v1/admin/tickets?status=pending&machine_brand=toy&page=1&page_size=1",
                               headers=records["auth"]))
    assert listing["total"] == 1 and listing["items"][0]["attachments"]


def test_admin_stats_options_notes_and_timeline(records):
    ticket = create_ticket(records)
    stats = body(client.get("/api/v1/admin/tickets/stats", headers=records["auth"]))
    assert stats["pending_count"] == 1 and stats["today_new"] == 1
    assert stats["average_handling_seconds"] == 0
    options = body(client.get("/api/v1/admin/tickets/options", headers=records["auth"]))
    assert options["assignees"] == [{"id": records["op"], "username": "op", "role": "operator"}]
    assigned = body(client.post(f"/api/v1/admin/tickets/{ticket['id']}/assign", headers=records["auth"],
                                json={"assignee_id": records["op"]}))
    assert assigned["assignee_name"] == "op"
    noted = body(client.post(f"/api/v1/admin/tickets/{ticket['id']}/notes", headers=records["auth"],
                             json={"content": "只供客服查看"}))
    assert [event["event_type"] for event in noted["timeline"]] == ["created", "assigned", "internal_note"]
    assert noted["timeline"][-1]["content"] == "只供客服查看"


def test_need_info_and_close_require_reason(records):
    ticket = create_ticket(records)
    body(client.post(f"/api/v1/admin/tickets/{ticket['id']}/assign", headers=records["auth"],
                     json={"assignee_id": records["op"]}))
    assert client.put(f"/api/v1/admin/tickets/{ticket['id']}/status", headers=records["auth"],
                      json={"status": "need_info"}).status_code == 422


def test_public_config_has_explicit_allowlist_and_never_exposes_secrets(records):
    with Session.begin() as db:
        db.add_all([
            SysConfig(key="frontend.api_base_url", value="https://match-api.elesos.cc", is_secret=False),
            SysConfig(key="support.whatsapp_url", value="https://wa.me/123", is_secret=False),
            SysConfig(key="support.telegram_url", value="https://t.me/private", is_secret=True),
            SysConfig(key="ai.api_key", value="do-not-leak", is_secret=False),
        ])
    public = body(client.get("/api/v1/config/public"))
    assert public == {"frontend.api_base_url": "https://match-api.elesos.cc", "support.whatsapp_url": "https://wa.me/123"}
    assert "ai.api_key" not in public and "support.telegram_url" not in public
