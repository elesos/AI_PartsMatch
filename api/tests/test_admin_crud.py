from __future__ import annotations

from io import BytesIO
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import (
    AdminUser, Base, CartItem, Machine, MachinePartRelation, MachineType, Part, PartCategory,
    PartCrossReference,
)
from app.services.catalog_validation import active_parts_statement

engine = create_engine(
    "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, _record):
    connection.execute("PRAGMA foreign_keys=ON")


TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)


def override_db():
    with TestingSession() as session:
        yield session


@pytest.fixture(autouse=True)
def isolated_database():
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_db
    with TestingSession() as db:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name == "part_category":
                db.execute(table.delete().where(table.c.parent_id.is_not(None)))
            db.execute(table.delete())
        admin = AdminUser(username="crud-admin", password_hash=hash_password("password"), role="admin")
        db.add_all([admin, MachineType(code="forklift", name="叉车", sort_order=10),
                    MachineType(code="excavator", name="挖掘机", sort_order=20)])
        db.commit()
        token, _ = create_access_token(admin)
    yield {"Authorization": f"Bearer {token}"}
    if previous_override is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous_override


client = TestClient(app, raise_server_exceptions=False)


def part_payload(index: int = 1, *, brand: str = "Toyota") -> dict:
    return {
        "sku": f"SKU-{brand}-{index}", "part_no": f"PN-{index}", "oem_no": f"OEM-{index}",
        "brand": brand, "category": "engine", "name_zh": f"滤芯 {index}",
        "name_en": f"Filter {index}", "name_vi": None, "specs": {"size": index},
        "price": "12.50", "stock": 5, "is_active": True,
    }


def create_part(headers, index: int = 1, brand: str = "Toyota") -> dict:
    response = client.post("/api/v1/admin/parts", json=part_payload(index, brand=brand), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def create_machine(headers) -> dict:
    response = client.post("/api/v1/admin/machines", json={
        "machine_type": "forklift", "brand": "Toyota", "model": "8FD30", "series": "8",
        "year": 2024, "region": "CN", "engine_model": "1DZ", "notes": "出口版",
    }, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_routes_require_authentication(isolated_database) -> None:
    response = client.get("/api/v1/admin/parts")
    assert response.status_code == 401


def test_part_crud_filters_validation_and_conflicts(isolated_database) -> None:
    headers = isolated_database
    part = create_part(headers)
    create_part(headers, 2, "CAT")
    listing = client.get("/api/v1/admin/parts?q=Filter&brand=Toyota&category=engine&page=1&page_size=1", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 1
    assert listing.json()["data"]["items"][0]["id"] == part["id"]

    payload = part_payload(3)
    payload["price"] = "-0.01"
    invalid = client.post("/api/v1/admin/parts", json=payload, headers=headers)
    assert invalid.status_code == 422
    assert invalid.json()["data"]["errors"][0]["loc"][-1] == "price"

    duplicate = part_payload(9)
    duplicate["part_no"] = part["part_no"]
    conflict = client.post("/api/v1/admin/parts", json=duplicate, headers=headers)
    assert conflict.status_code == 422
    assert conflict.json()["data"]["reason"] == "not_unique"

    update = part_payload(1)
    update["name_zh"] = "新名称"
    updated = client.put(f"/api/v1/admin/parts/{part['id']}", json=update, headers=headers)
    assert updated.json()["data"]["name_zh"] == "新名称"
    deleted = client.delete(f"/api/v1/admin/parts/{part['id']}", headers=headers)
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/admin/parts/{part['id']}", headers=headers).json()["data"]["is_active"] is False


def test_part_image_reuses_storage_service(isolated_database, monkeypatch) -> None:
    headers = isolated_database
    part = create_part(headers)

    async def fake_upload(_service, upload, **kwargs):
        class Uploaded:
            id = "file-1"
            url = "https://assets.example/part.jpg"
        return Uploaded()

    monkeypatch.setattr("app.routers.admin_crud.StorageService.upload", fake_upload)
    response = client.post(
        f"/api/v1/admin/parts/{part['id']}/images?sort_order=2", headers=headers,
        files={"file": ("part.jpg", BytesIO(b"image"), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["file_id"] == "file-1"
    assert client.get(f"/api/v1/admin/parts/{part['id']}", headers=headers).json()["data"]["images"][0]["sort_order"] == 2


def test_parts_extended_fields_sort_options_export_bulk_and_operator_read_only(isolated_database) -> None:
    headers = isolated_database
    first_payload = part_payload(1); first_payload.update({
        "alternate_no": "ALT-1", "unit": "套", "stock_status": "low_stock", "notes": "critical",
    })
    first = client.post("/api/v1/admin/parts", json=first_payload, headers=headers).json()["data"]
    second = create_part(headers, 2, "CAT")
    assert first["alternate_no"] == "ALT-1" and first["unit"] == "套" and first["notes"] == "critical"
    listing = client.get("/api/v1/admin/parts?sort_by=sku&sort_dir=asc", headers=headers).json()["data"]
    assert [item["sku"] for item in listing["items"]] == sorted([first["sku"], second["sku"]])
    options = client.get("/api/v1/admin/parts/options", headers=headers).json()["data"]
    assert set(options["brands"]) == {"Toyota", "CAT"} and "engine" in options["categories"]
    exported = client.get(f"/api/v1/admin/parts/export?ids={first['id']}", headers=headers)
    assert exported.status_code == 200 and exported.content.startswith(b"\xef\xbb\xbf") and b"ALT-1" in exported.content
    bulk = client.post("/api/v1/admin/parts/bulk", headers=headers, json={
        "ids": [first["id"], "missing"], "action": "deactivate",
    }).json()["data"]
    assert bulk["updated"] == [first["id"]] and bulk["partial_success"] is True and bulk["errors"][0]["id"] == "missing"

    with TestingSession() as db:
        operator = AdminUser(username="catalog-reader", password_hash=hash_password("password"), role="operator")
        db.add(operator); db.commit(); operator_token, _ = create_access_token(operator)
    operator_headers = {"Authorization": f"Bearer {operator_token}"}
    assert client.get("/api/v1/admin/parts", headers=operator_headers).status_code == 200
    assert client.post("/api/v1/admin/parts", headers=operator_headers, json=part_payload(9)).status_code == 403
    assert client.post("/api/v1/admin/parts/bulk", headers=operator_headers,
                       json={"ids": [second["id"]], "action": "deactivate"}).status_code == 403


def test_part_image_type_primary_sort_delete_and_storage_cleanup(isolated_database, monkeypatch) -> None:
    headers, part = isolated_database, create_part(isolated_database)
    serial = iter(["file-a", "file-b"]); deleted = []
    async def fake_upload(_service, _upload, **kwargs):
        file_id = next(serial)
        return type("Uploaded", (), {"id": file_id, "url": f"https://assets.example/{file_id}.jpg"})()
    def fake_delete(_service, file_id): deleted.append(file_id)
    monkeypatch.setattr("app.routers.admin_crud.StorageService.upload", fake_upload)
    monkeypatch.setattr("app.routers.admin_crud.StorageService.delete", fake_delete)
    first = client.post(f"/api/v1/admin/parts/{part['id']}/images?sort_order=0&image_type=product", headers=headers,
                        files={"file": ("a.jpg", BytesIO(b"image"), "image/jpeg")}).json()["data"]
    second = client.post(f"/api/v1/admin/parts/{part['id']}/images?sort_order=2&image_type=nameplate", headers=headers,
                         files={"file": ("b.jpg", BytesIO(b"image"), "image/jpeg")}).json()["data"]
    assert second["image_type"] == "nameplate"
    primary = client.patch(f"/api/v1/admin/parts/{part['id']}/images/{second['id']}/primary", headers=headers).json()["data"]
    assert primary["sort_order"] == 0
    changed = client.put(f"/api/v1/admin/parts/{part['id']}/images/{first['id']}", headers=headers,
                         json={"sort_order": 7, "image_type": "packaging"}).json()["data"]
    assert changed["sort_order"] == 7 and changed["image_type"] == "packaging"
    assert client.delete(f"/api/v1/admin/parts/{part['id']}/images/{first['id']}", headers=headers).status_code == 200
    assert deleted == ["file-a"]


def test_machine_crud_and_filtering(isolated_database) -> None:
    headers = isolated_database
    machine = create_machine(headers)
    listing = client.get("/api/v1/admin/machines?brand=Toyota&machine_type=forklift", headers=headers)
    assert listing.json()["data"]["total"] == 1
    payload = {key: machine[key] for key in ("machine_type", "brand", "model", "series", "year", "region", "engine_model", "notes")}
    payload["model"] = "8FD35"
    assert client.put(f"/api/v1/admin/machines/{machine['id']}", json=payload, headers=headers).json()["data"]["model"] == "8FD35"
    assert client.delete(f"/api/v1/admin/machines/{machine['id']}", headers=headers).status_code == 200


def test_machine_part_crud_csv_and_foreign_key_errors(isolated_database) -> None:
    headers = isolated_database
    machine, part = create_machine(headers), create_part(headers)
    payload = {"machine_id": machine["id"], "part_id": part["id"], "system": "engine", "priority": 4}
    created = client.post("/api/v1/admin/relations/machine-part", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    relation_id = created.json()["data"]["id"]
    assert client.get(f"/api/v1/admin/relations/machine-part/{relation_id}", headers=headers).status_code == 200
    assert client.delete(f"/api/v1/admin/relations/machine-part/{relation_id}", headers=headers).status_code == 200

    csv_data = f"machine_id,part_id,system,priority\n{machine['id']},{part['id']},engine,8\n"
    imported = client.post("/api/v1/admin/relations/machine-part/import", headers=headers,
                           files={"file": ("relations.csv", csv_data, "text/csv")})
    assert imported.status_code == 201, imported.text
    assert imported.json()["data"] == {"created": 1, "valid": 1, "processed": 1, "dry_run": False, "errors": []}

    payload["machine_id"] = "missing-machine"
    missing = client.post("/api/v1/admin/relations/machine-part", json=payload, headers=headers)
    assert missing.status_code == 422
    assert missing.json()["data"]["reason"] == "invalid_foreign_key"


def test_machine_types_options_permissions_and_in_use_conflicts(isolated_database) -> None:
    headers = isolated_database
    created = client.post("/api/v1/admin/machine-types", headers=headers, json={
        "code": "telehandler", "name": "伸缩臂叉装车", "sort_order": 40, "is_active": True,
    })
    assert created.status_code == 201, created.text
    type_id = created.json()["data"]["id"]
    machine = client.post("/api/v1/admin/machines", headers=headers, json={
        "machine_type": "telehandler", "brand": "JCB", "model": "540-170", "series": None,
        "year": 2025, "region": "EU", "engine_model": "EcoMAX", "notes": "stage V",
    })
    assert machine.status_code == 201 and machine.json()["data"]["notes"] == "stage V"
    options = client.get("/api/v1/admin/machines/options", headers=headers).json()["data"]
    assert "JCB" in options["brands"] and any(item["code"] == "telehandler" for item in options["types"])
    assert client.delete(f"/api/v1/admin/machine-types/{type_id}", headers=headers).status_code == 422
    invalid = client.post("/api/v1/admin/machines", headers=headers, json={
        "machine_type": "hard-coded-missing", "brand": "X", "model": "Y",
    })
    assert invalid.status_code == 422 and invalid.json()["data"]["field"] == "machine_type"

    with TestingSession() as db:
        operator = AdminUser(username="machine-reader", password_hash=hash_password("password"), role="operator")
        db.add(operator); db.commit(); token, _ = create_access_token(operator)
    operator_headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/admin/machines", headers=operator_headers).status_code == 200
    assert client.get("/api/v1/admin/machine-types", headers=operator_headers).status_code == 200
    assert client.post("/api/v1/admin/machine-types", headers=operator_headers, json={
        "code": "grader", "name": "平地机",
    }).status_code == 403


def test_machine_relation_enrichment_csv_preview_duplicates_and_partial_success(isolated_database) -> None:
    headers, machine = isolated_database, create_machine(isolated_database)
    first, second = create_part(headers, 1), create_part(headers, 2)
    csv_data = (
        "part_id,system,position,serial_from,serial_to,priority,is_active,notes\n"
        f"{first['id']},engine,left,S001,S999,8,true,primary\n"
        f"{first['id']},engine,right,,,7,true,duplicate in file\n"
        "missing-part,hydraulic,,,,2,true,invalid foreign key\n"
        f"{second['id']},filter,rear,,,4,false,regional\n"
    )
    preview = client.post(
        f"/api/v1/admin/relations/machine-part/import?machine_id={machine['id']}&dry_run=true",
        headers=headers, files={"file": ("fitments.csv", csv_data, "text/csv")},
    )
    assert preview.status_code == 201, preview.text
    preview_data = preview.json()["data"]
    assert preview_data["created"] == 0 and preview_data["valid"] == 2 and preview_data["processed"] == 4
    assert {error["reason"] for error in preview_data["errors"]} == {"not_unique", "invalid_foreign_key"}
    imported = client.post(
        f"/api/v1/admin/relations/machine-part/import?machine_id={machine['id']}",
        headers=headers, files={"file": ("fitments.csv", csv_data, "text/csv")},
    ).json()["data"]
    assert imported["created"] == 2 and len(imported["errors"]) == 2
    listing = client.get(f"/api/v1/admin/relations/machine-part?machine_id={machine['id']}", headers=headers).json()["data"]
    assert listing["total"] == 2
    assert {item["part_no"] for item in listing["items"]} == {first["part_no"], second["part_no"]}
    assert any(item["is_active"] is False and item["notes"] == "regional" for item in listing["items"])


def test_cross_refs_bidirectional_search_and_conflicts(isolated_database) -> None:
    headers = isolated_database
    left, right = create_part(headers, 1), create_part(headers, 2)
    payload = {"source_part_id": left["id"], "target_part_id": right["id"],
               "relation_type": "replacement", "reliability": "0.9000", "restrictions": None}
    created = client.post("/api/v1/admin/cross-refs", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    assert client.get(f"/api/v1/admin/cross-refs?part_number={right['part_no']}", headers=headers).json()["data"]["total"] == 1
    payload["source_part_id"], payload["target_part_id"] = payload["target_part_id"], payload["source_part_id"]
    conflict = client.post("/api/v1/admin/cross-refs", json=payload, headers=headers)
    assert conflict.status_code == 422
    assert "either direction" in conflict.json()["message"]


def test_cross_ref_workflow_cycle_filters_public_visibility_and_operator_read_only(isolated_database) -> None:
    headers = isolated_database
    first, second, third, hidden = [create_part(headers, index) for index in range(10, 14)]

    def relation(source: dict, target: dict, **values) -> dict:
        payload = {
            "source_part_id": source["id"], "target_part_id": target["id"],
            "relation_type": "replacement", "reliability": "0.9500", "restrictions": "CN only",
            "brand": "verified", "priority": 20, "source": "OEM bulletin", "notes": "reviewed",
            "status": "active",
        }
        payload.update(values)
        response = client.post("/api/v1/admin/cross-refs", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        return response.json()["data"]

    first_second = relation(first, second)
    relation(second, third, priority=10)
    relation(first, hidden, status="inactive", priority=99)

    listing = client.get(
        f"/api/v1/admin/cross-refs?q={second['part_no']}&status=active&part_id={second['id']}"
        "&direction=target&sort_by=priority&sort_dir=desc", headers=headers,
    )
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 1
    item = listing.json()["data"]["items"][0]
    assert item["source_part"]["part_no"] == first["part_no"]
    assert item["target_part"]["part_no"] == second["part_no"]
    assert item["quality"] == "high" and item["priority"] == 20 and item["source"] == "OEM bulletin"

    duplicate = client.get(
        "/api/v1/admin/cross-refs/conflicts",
        params={"source_part_id": second["id"], "target_part_id": first["id"]}, headers=headers,
    ).json()["data"]
    assert duplicate["can_save"] is False
    assert duplicate["conflicts"][0]["type"] == "reverse_duplicate"
    assert duplicate["conflicts"][0]["action"]["kind"] == "edit_existing"

    cycle = client.get(
        "/api/v1/admin/cross-refs/conflicts",
        params={"source_part_id": third["id"], "target_part_id": first["id"]}, headers=headers,
    ).json()["data"]
    assert cycle["can_save"] is False and cycle["conflicts"][0]["type"] == "cycle"
    assert [node["part_no"] for node in cycle["conflicts"][0]["path"]] == [
        third["part_no"], first["part_no"], second["part_no"], third["part_no"],
    ]
    blocked = client.post("/api/v1/admin/cross-refs", json={
        "source_part_id": third["id"], "target_part_id": first["id"],
        "relation_type": "replacement", "reliability": 1, "status": "active",
    }, headers=headers)
    assert blocked.status_code == 422 and blocked.json()["data"]["reason"] == "cycle"
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(PartCrossReference)) == 3

    public_detail = client.get(f"/api/v1/parts/{first['id']}").json()["data"]
    assert {item["part"]["id"] for item in public_detail["alternatives"]} == {second["id"]}

    with TestingSession() as db:
        operator = AdminUser(username="xref-operator", password_hash=hash_password("password"), role="operator")
        db.add(operator); db.commit(); operator_token, _ = create_access_token(operator)
    operator_headers = {"Authorization": f"Bearer {operator_token}"}
    assert client.get("/api/v1/admin/cross-refs", headers=operator_headers).status_code == 200
    assert client.get(
        "/api/v1/admin/cross-refs/conflicts",
        params={"source_part_id": first["id"], "target_part_id": third["id"]}, headers=operator_headers,
    ).status_code == 200
    assert client.put(f"/api/v1/admin/cross-refs/{first_second['id']}", headers=operator_headers,
                      json={"source_part_id": first["id"], "target_part_id": second["id"],
                            "relation_type": "OEM", "reliability": 1, "status": "active"}).status_code == 403
    assert client.delete(f"/api/v1/admin/cross-refs/{first_second['id']}", headers=operator_headers).status_code == 403


def test_alias_review_workflow(isolated_database) -> None:
    headers, part = isolated_database, create_part(isolated_database)
    payload = {"part_id": part["id"], "alias": "空滤", "language": "zh", "region": "CN",
               "source": "operator", "status": "pending"}
    created = client.post("/api/v1/admin/aliases", json=payload, headers=headers)
    alias_id = created.json()["data"]["id"]
    reviewed = client.patch(f"/api/v1/admin/aliases/{alias_id}/status", json={"status": "active"}, headers=headers)
    assert reviewed.json()["data"]["status"] == "active"
    repeated = client.patch(f"/api/v1/admin/aliases/{alias_id}/status", json={"status": "rejected"}, headers=headers)
    assert repeated.status_code == 422
    trimmed = client.post("/api/v1/admin/aliases", json={**payload, "alias": "  Hydraulic Filter  ", "language": "EN"}, headers=headers)
    assert trimmed.status_code == 201 and trimmed.json()["data"]["alias"] == "Hydraulic Filter"
    duplicate = client.post("/api/v1/admin/aliases", json={**payload, "alias": "hydraulic filter", "language": "en"}, headers=headers)
    assert duplicate.status_code == 422 and duplicate.json()["data"]["field"] == "alias"


def test_category_two_level_crud_and_slug_conflict(isolated_database) -> None:
    headers = isolated_database
    root = client.post("/api/v1/admin/categories", json={
        "name": "发动机", "slug": "engine", "parent_id": None, "sort_order": 1, "is_active": True,
    }, headers=headers).json()["data"]
    child = client.post("/api/v1/admin/categories", json={
        "name": "冷却", "slug": "cooling", "parent_id": root["id"], "sort_order": 1, "is_active": True,
    }, headers=headers)
    assert child.status_code == 201, child.text
    too_deep = client.post("/api/v1/admin/categories", json={
        "name": "水泵", "slug": "water-pump", "parent_id": child.json()["data"]["id"],
        "sort_order": 1, "is_active": True,
    }, headers=headers)
    assert too_deep.status_code == 422
    duplicate = client.post("/api/v1/admin/categories", json={
        "name": "另一个", "slug": "engine", "parent_id": None, "sort_order": 2, "is_active": True,
    }, headers=headers)
    assert duplicate.status_code == 422


def test_seed_is_idempotent_and_meets_catalogue_minimums(isolated_database, monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location("catalog_seed", Path(__file__).parents[1] / "scripts" / "seed.py")
    assert spec and spec.loader
    seed_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed_module)

    monkeypatch.setattr(seed_module, "SessionLocal", TestingSession)
    seed_module.seed()
    second = seed_module.seed()
    assert all(value == 0 for value in second.values())
    with TestingSession() as db:
        for brand in seed_module.BRANDS:
            parts = list(db.scalars(select(Part).where(Part.brand == brand)))
            ids = [part.id for part in parts]
            cross_refs = db.scalar(select(func.count()).select_from(PartCrossReference).where(
                PartCrossReference.source_part_id.in_(ids), PartCrossReference.target_part_id.in_(ids)
            ))
            assert len(parts) >= 10
            assert cross_refs >= 3
        assert db.scalar(select(func.count()).select_from(MachinePartRelation)) >= 30
        assert db.scalar(select(func.count()).select_from(PartCategory)) >= 5


def test_inactive_parts_are_excluded_and_cannot_enter_cart(isolated_database) -> None:
    with TestingSession() as db:
        part = Part(**part_payload())
        part.is_active = False
        db.add(part)
        db.commit()
        assert db.scalar(active_parts_statement().where(Part.id == part.id)) is None
        db.add(CartItem(session_id="test-session", part_id=part.id, quantity=1))
        with pytest.raises(AppError, match="inactive parts"):
            db.commit()
