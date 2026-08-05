from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import (AdminUser, AiMatchEvidence, Base, CartItem, FileObject, KnowledgeCandidate, LlmCallLog,
                        Part, PartQueryLog, QueryLogCorrection)

engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Session = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)
client = TestClient(app)

def override_db():
    with Session() as db: yield db

@pytest.fixture(autouse=True)
def records():
    previous = app.dependency_overrides.get(get_db); app.dependency_overrides[get_db] = override_db
    with Session.begin() as db:
        for table in reversed(Base.metadata.sorted_tables): db.execute(table.delete())
        admin = AdminUser(username="log-admin", password_hash=hash_password("password123"), role="admin", is_active=True)
        operator = AdminUser(username="log-operator", password_hash=hash_password("password123"), role="operator", is_active=True)
        recommended = Part(sku="QL-1", part_no="WRONG-1", brand="CAT", name_zh="错误件", specs={}, stock=2, is_active=True)
        correct = Part(sku="QL-2", part_no="RIGHT-2", brand="CAT", name_zh="正确件", specs={}, stock=3, is_active=True)
        file = FileObject(object_key="query/nameplate.jpg", original_name="nameplate.jpg", mime_type="image/jpeg", size=20,
                          url="https://assets.example/nameplate.jpg?token=provider-secret", owner_key="session:s")
        db.add_all([admin, operator, recommended, correct, file]); db.flush()
        log = PartQueryLog(session_id="s", client_ip="198.51.100.1", query_type="image",
            query_text="Buyer buyer@example.com +86 13812341234 needs CAT filter",
            request_data={"image_ids":[file.id],"contact_info":"buyer@example.com","api_key":"raw-secret"},
            raw_input={"image_ids":[file.id],"note":"call 13812341234"}, extracted_info={"part_no":"WRONG-1"},
            ai_result={"provider":"rules"}, result_count=1, confidence=Decimal("0.8200"), match_status="high",
            need_manual=True, duration_ms=47, created_at=datetime.now(UTC))
        excel = PartQueryLog(session_id="s", query_type="excel", source_id="batch-1", query_text="parts.xlsx",
            request_data={"batch_id":"batch-1"}, result_count=0, need_manual=False, created_at=datetime.now(UTC))
        manual = PartQueryLog(session_id="s", query_type="manual", source_id="ticket-1", query_text="unknown seal",
            request_data={"ticket_id":"ticket-1"}, result_count=0, match_status="insufficient", need_manual=True,
            created_at=datetime.now(UTC))
        db.add_all([log, excel, manual]); db.flush()
        db.add_all([AiMatchEvidence(query_log_id=log.id, part_id=recommended.id, confidence=Decimal("0.8200"),
            reason="email buyer@example.com", evidence=[{"type":"ocr","content":"13812341234"}]),
            LlmCallLog(query_log_id=log.id, provider="openai-compatible", api_mode="responses", model="configured",
                prompt_hash="a"*64, safety_identifier="b"*64, input_tokens=10, output_tokens=3, duration_ms=31, status="success"),
            CartItem(owner_key="session:s", session_id="s", part_id=recommended.id, quantity=1, match_status="high",
                     confidence=Decimal("0.8200"), source="ai", query_id=log.id)])
        admin_token,_=create_access_token(admin); operator_token,_=create_access_token(operator)
        result={"log":log.id,"recommended":recommended.id,"correct":correct.id,
                "admin":{"Authorization":f"Bearer {admin_token}"},"operator":{"Authorization":f"Bearer {operator_token}"}}
    yield result
    if previous is None: app.dependency_overrides.pop(get_db,None)
    else: app.dependency_overrides[get_db]=previous

def test_list_filters_and_real_utc_stats(records):
    data=client.get("/api/v1/admin/query-logs",params={"source":"excel","q":"parts"},headers=records["operator"]).json()["data"]
    assert data["total"]==1 and data["items"][0]["source"]=="excel" and data["items"][0]["source_id"]=="batch-1"
    assert client.get("/api/v1/admin/query-logs",params={"source":"manual"},headers=records["operator"]).json()["data"]["total"]==1
    stats=client.get("/api/v1/admin/query-logs/stats",headers=records["operator"]).json()["data"]
    assert stats["query_count"]==3 and stats["exact_count"]==0 and stats["manual_count"]==2
    assert stats["exact_rate"]==0 and stats["manual_rate"]==pytest.approx(2/3)

def test_detail_redacts_contacts_and_provider_secrets(records):
    response=client.get(f"/api/v1/admin/query-logs/{records['log']}",headers=records["operator"])
    assert response.status_code==200; data=response.json()["data"]; serialized=str(data)
    assert "buyer@example.com" not in serialized and "13812341234" not in serialized and "raw-secret" not in serialized
    assert "prompt_hash" not in serialized and "safety_identifier" not in serialized and data["client_ip"]=="[REDACTED]"
    assert data["candidates"][0]["part_no"]=="WRONG-1" and data["selected_parts"][0]["source"]=="ai"
    assert data["uploaded_files"][0]["url"]=="https://assets.example/nameplate.jpg"

def test_correction_admin_only_append_only_and_creates_candidate(records):
    payload={"recommended_part_id":records["recommended"],"correct_part_id":records["correct"],"reason":"OCR digit misread; catalogue confirms RIGHT-2"}
    url=f"/api/v1/admin/query-logs/{records['log']}/corrections"
    assert client.post(url,json=payload,headers=records["operator"]).status_code==403
    assert client.post(url,json=payload,headers=records["admin"]).status_code==201
    assert client.post(url,json=payload,headers=records["admin"]).status_code==409
    with Session() as db:
        correction=db.scalar(select(QueryLogCorrection)); candidate=db.scalar(select(KnowledgeCandidate).where(KnowledgeCandidate.query_correction_id==correction.id)); original=db.get(PartQueryLog,records["log"])
        assert correction.actor_id and correction.status==candidate.status=="pending_review"
        assert candidate.ticket_id is None and original.match_status=="high" and original.confidence==Decimal("0.8200")
