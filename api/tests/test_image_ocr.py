from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.exceptions import AppError
from app.main import app
from app.models import AiMatchEvidence, Base, FileObject, Part, PartQueryLog, SysConfig
from app.services.image_ocr import HttpOCRProvider, LocalTesseractProvider, classify_image, extract_fields
from app.services.storage import StorageService


engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, _record):
    connection.execute("PRAGMA foreign_keys=ON")


TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)


def override_db():
    with TestingSession() as session:
        yield session


client = TestClient(app)
JPEG = b"\xff\xd8\xff\xe0" + b"valid-jpeg-test-body"


@pytest.fixture(autouse=True)
def image_data(monkeypatch):
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_db
    with TestingSession.begin() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.add_all([
            FileObject(
                id="img-a", object_key="uploads/a.jpg", original_name="a.jpg", mime_type="image/jpeg",
                size=len(JPEG), url="https://assets.test/a.jpg", owner_key="session:owner",
            ),
            FileObject(
                id="img-b", object_key="uploads/b.jpg", original_name="b.jpg", mime_type="image/jpeg",
                size=len(JPEG), url="https://assets.test/b.jpg", owner_key="session:other",
            ),
            FileObject(
                id="img-heic", object_key="uploads/a.heic", original_name="a.heic", mime_type="image/heic",
                size=16, url="https://assets.test/a.heic", owner_key="session:owner",
            ),
            SysConfig(key="ocr.provider", value="mock", value_type="str", is_secret=False),
        ])
    monkeypatch.setattr(StorageService, "read", lambda self, record: JPEG)
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def set_config(key, value, *, secret=False):
    with TestingSession.begin() as db:
        item = db.get(SysConfig, key)
        if item:
            item.value = value
        else:
            db.add(SysConfig(key=key, value=value, value_type="json", is_secret=secret))


def data(response, status=200):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "data"}
    return body


@pytest.mark.asyncio
async def test_t1_rejects_extension_mime_magic_disagreement_and_executable():
    service = object.__new__(StorageService)
    for filename, mime, content in [
        ("evil.jpg", "image/jpeg", b"MZ executable"),
        ("renamed.png", "image/png", JPEG),
        ("wrong.webp", "image/jpeg", b"RIFFxxxxWEBPpayload"),
    ]:
        with pytest.raises(AppError) as error:
            await service.upload(UploadFile(filename=filename, file=BytesIO(content), headers={"content-type": mime}))
        assert error.value.code == "INVALID_IMAGE"


def test_t1_upload_requires_session_and_enforces_five_before_storage():
    no_session = client.post("/api/v1/images/upload", files=[("files", ("a.jpg", JPEG, "image/jpeg"))])
    assert data(no_session, 400)["code"] == "SESSION_REQUIRED"
    six = [("files", (f"{n}.jpg", JPEG, "image/jpeg")) for n in range(6)]
    assert client.post("/api/v1/images/upload", headers={"X-Session-ID": "owner"}, files=six).status_code == 422


def test_t2_ocr_lines_empty_blurry_and_owner_isolation():
    set_config("ocr.mock_text", "Part No: AB-12\nSerial No: SN99")
    result = data(client.post("/api/v1/images/img-a/ocr", headers={"X-Session-ID": "owner"}))["data"]
    assert result["lines"] == ["Part No: AB-12", "Serial No: SN99"]
    assert data(client.post("/api/v1/images/img-b/ocr", headers={"X-Session-ID": "owner"}), 404)["code"] == "IMAGE_NOT_FOUND"

    with TestingSession.begin() as db:
        record = db.get(FileObject, "img-a")
        record.ocr_text = record.ocr_lines = None
    set_config("ocr.mock_text", "")
    assert data(client.post("/api/v1/images/img-a/ocr", headers={"X-Session-ID": "owner"}), 422)["code"] == "OCR_EMPTY"
    set_config("ocr.mock_text", "readable")
    set_config("ocr.mock_blur_score", 0.1)
    set_config("ocr.blur_threshold", 0.5)
    assert data(client.post("/api/v1/images/img-a/ocr", headers={"X-Session-ID": "owner"}), 422)["code"] == "IMAGE_BLURRY"


def test_t2_heic_contract_is_explicit_for_local_provider():
    response = client.post("/api/v1/images/img-heic/ocr", headers={"X-Session-ID": "owner"})
    assert data(response, 422)["code"] == "HEIC_OCR_UNSUPPORTED"


@pytest.mark.asyncio
async def test_t2_real_local_tesseract_reads_generated_clear_part_number():
    canvas = Image.new("RGB", (1000, 220), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=72)
    draw.text((30, 55), "PART NO: AB12345", fill="black", font=font)
    encoded = BytesIO()
    canvas.save(encoded, format="PNG")
    with TestingSession() as db:
        from app.services.config_service import ConfigService
        provider = LocalTesseractProvider(ConfigService(db))
        payload = await provider.recognize(encoded.getvalue(), "image/png", "generated")
    normalized = payload.text.upper().replace(" ", "").replace("-", "")
    assert "AB12345" in normalized
    assert payload.blur_score > 0


@pytest.mark.asyncio
async def test_t2_http_provider_caps_timeout_and_does_not_leak_secret(monkeypatch):
    set_config("ocr.http.endpoint", "https://ocr.invalid/recognize")
    set_config("ocr.http.api_key", "TOP-SECRET", secret=True)
    set_config("ocr.http.timeout_seconds", 99)
    with TestingSession() as db:
        from app.services.config_service import ConfigService
        provider = HttpOCRProvider(ConfigService(db))
    assert provider.timeout == 10.0

    class FailingClient:
        def __init__(self, *, timeout):
            assert timeout.connect == 10.0
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            return None
        async def post(self, *_args, **_kwargs):
            raise httpx.ReadTimeout("TOP-SECRET")

    monkeypatch.setattr(httpx, "AsyncClient", FailingClient)
    with pytest.raises(AppError) as error:
        await provider.recognize(JPEG, "image/jpeg", "img-a")
    assert error.value.code == "OCR_TIMEOUT"
    assert "TOP-SECRET" not in error.value.message


def test_t3_rules_cover_required_image_classes_and_dynamic_threshold():
    assert classify_image("Engine Model: 1DZ-II Engine No: E1")[0] == "engine_nameplate"
    assert classify_image("Machine Model: 8FD30 Serial No: S1")[0] == "machine_nameplate"
    assert classify_image("Part Number: AB12 OEM: O1")[0] == "old_part_number"
    assert classify_image("Barcode Qty 10")[0] == "package_label"
    assert classify_image("Exploded diagram item no 4")[0] == "exploded_diagram"
    assert classify_image("filter bearing")[0] == "part_photo"
    assert classify_image("Part Number: AB12", threshold=0.9)[0] == "unknown"


def test_t4_parse_extracts_nameplate_and_part_fields():
    text = "Brand: Toyota\nMachine Model: 8FD30\nSerial No: SN-1\nEngine Model: 1DZ-II\nYear: 2024\nPart No: AB-12\nOEM: OEM-9"
    set_config("ocr.mock_text", text)
    result = data(client.post("/api/v1/images/img-a/parse", headers={"X-Session-ID": "owner"}))["data"]
    assert result["image_type"] == "machine_nameplate"
    assert result["extracted_info"] == {
        "machine_brand": "Toyota", "machine_model": "8FD30", "serial_number": "SN-1",
        "engine_model": "1DZ-II", "year": 2024, "part_no": "AB-12", "oem_no": "OEM-9",
    }
    assert extract_fields(text)["engine_model"] == "1DZ-II"


def test_t5_t6_t7_match_multiple_candidates_logs_and_evidence():
    with TestingSession.begin() as db:
        db.add_all([
            Part(sku="A", part_no="A-1", oem_no="OEM-9", brand="One", name_zh="一", name_en="One", name_vi="Một", specs={}, stock=1, is_active=True),
            Part(sku="B", part_no="B-1", oem_no="OEM-9", brand="Two", name_zh="二", name_en="Two", name_vi="Hai", specs={}, stock=1, is_active=True),
        ])
    set_config("ocr.mock_text", "OEM: OEM-9")
    result = data(client.post(
        "/api/v1/images/match", headers={"X-Session-ID": "owner"},
        json={"image_ids": ["img-a"], "user_hint": "please match", "lang": "vi"},
    ))["data"]
    assert result["match_status"] == "multiple"
    assert {item["part"]["part_no"] for item in result["candidates"]} == {"A-1", "B-1"}
    assert {item["part"]["name"] for item in result["candidates"]} == {"Một", "Hai"}
    with TestingSession() as db:
        log = db.scalar(select(PartQueryLog).where(PartQueryLog.id == result["query_id"]))
        assert log.query_type == "image"
        assert log.raw_input == {"image_ids": ["img-a"]}
        assert log.extracted_info["oem_no"] == "OEM-9"
        assert log.ai_result["match_status"] == "multiple"
        evidence = list(db.scalars(select(AiMatchEvidence).where(AiMatchEvidence.query_log_id == log.id)))
        assert len(evidence) == 2 and all(row.evidence["image_ids"] == ["img-a"] for row in evidence)


def test_t6_only_machine_model_returns_guidance_and_not_found_is_logged():
    set_config("ocr.mock_text", "Machine Model: 8FD30")
    result = data(client.post(
        "/api/v1/images/match", headers={"X-Session-ID": "owner"}, json={"image_ids": ["img-a"]},
    ))["data"]
    assert result["match_status"] == "not_found"
    assert result["extracted_info"]["machine_model"] == "8FD30"
    assert "选择配件系统" in result["suggestions"][0]


def test_t7_postgresql_migration_contains_required_columns_and_reversible_index():
    migration = (Path(__file__).parents[1] / "migrations/versions/c28b91e7d4a2_image_ocr.py").read_text()
    for column in ("owner_key", "raw_input", "extracted_info", "ai_result"):
        assert f'"{column}"' in migration
    assert 'op.create_index("ix_file_object_owner_key"' in migration
    assert 'op.drop_index("ix_file_object_owner_key"' in migration
