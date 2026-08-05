from __future__ import annotations

import csv
import io
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import String, and_, asc, desc, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.responses import success
from app.core.security import require_admin_write
from app.models import (
    AdminUser, Machine, MachinePartRelation, MachineType, Part, PartAlias, PartCategory,
    PartCrossReference, PartImage,
)
from app.schemas.admin_crud import (
    AliasCreate, AliasResult, AliasStatusUpdate, AliasUpdate, CategoryCreate,
    CategoryResult, CategoryUpdate, CrossRefCreate, CrossRefResult, CrossRefUpdate,
    CsvImportResult, MachineCreate, MachinePartCreate, MachinePartResult, MachineTypeCreate,
    MachineTypeResult, MachineTypeUpdate, PartBulkRequest, PartImageUpdate,
    MachinePartUpdate, MachineResult, MachineUpdate, PartCreate, PartImageResult,
    PartResult, PartUpdate,
)
from app.services.storage import StorageService

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin data"],
    dependencies=[Depends(require_admin_write)],
)
ModelT = TypeVar("ModelT")


def _page(db: Session, statement: Any, model: Any, page: int, page_size: int) -> tuple[list[Any], int]:
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    items = list(db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all())
    return items, total


def _page_data(items: list[Any], total: int, page: int, page_size: int) -> dict[str, Any]:
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _get_or_404(db: Session, model: type[ModelT], object_id: str, label: str) -> ModelT:
    item = db.get(model, object_id)
    if item is None:
        raise AppError(f"{label} not found", code=40401, status_code=404)
    return item


def _integrity_error(error: IntegrityError) -> AppError:
    text = str(error.orig).lower()
    if "foreign key" in text:
        return AppError(
            "referenced record does not exist or is still in use",
            code=42202, status_code=422, data={"field": "reference", "reason": "invalid_foreign_key"},
        )
    field = "part_no" if "brand" in text and "part_no" in text else "value"
    if "sku" in text:
        field = "sku"
    elif "slug" in text:
        field = "slug"
    return AppError(
        "record conflicts with an existing value",
        code=42201, status_code=422, data={"field": field, "reason": "not_unique"},
    )


def _save(db: Session, item: ModelT) -> ModelT:
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    except IntegrityError as error:
        db.rollback()
        raise _integrity_error(error) from error


def _delete(db: Session, item: Any) -> None:
    try:
        db.delete(item)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise _integrity_error(error) from error


def _part_dict(db: Session, item: Part) -> dict[str, Any]:
    data = PartResult.model_validate(item).model_dump()
    images = db.scalars(
        select(PartImage).where(PartImage.part_id == item.id).order_by(PartImage.sort_order, PartImage.created_at)
    ).all()
    data["images"] = [PartImageResult.model_validate(image).model_dump() for image in images]
    return data


# Parts
@router.get("/parts")
def list_parts(
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(default=None, max_length=150),
    category: str | None = Query(default=None, max_length=100),
    brand: str | None = Query(default=None, max_length=100),
    is_active: bool | None = None,
    sort_by: str = Query(default="created_at", pattern="^(sku|part_no|oem_no|name_zh|brand|category|price|stock|is_active|created_at)$"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    sort_column = getattr(Part, sort_by)
    statement = select(Part).order_by((asc if sort_dir == "asc" else desc)(sort_column), Part.id)
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(Part.sku.ilike(pattern), Part.part_no.ilike(pattern),
                                        Part.oem_no.ilike(pattern), Part.name_zh.ilike(pattern),
                                        Part.name_en.ilike(pattern), Part.name_vi.ilike(pattern)))
    if category:
        statement = statement.where(Part.category == category)
    if brand:
        statement = statement.where(Part.brand == brand)
    if is_active is not None:
        statement = statement.where(Part.is_active == is_active)
    items, total = _page(db, statement, Part, page, page_size)
    return success(_page_data([_part_dict(db, item) for item in items], total, page, page_size))


@router.get("/parts/options")
def part_options(db: Annotated[Session, Depends(get_db)]) -> dict:
    brands = list(db.scalars(select(Part.brand).where(Part.brand != "").distinct().order_by(Part.brand)))
    used = set(db.scalars(select(Part.category).where(Part.category.is_not(None), Part.category != "").distinct()))
    configured = set(db.scalars(select(PartCategory.slug).where(PartCategory.is_active.is_(True))))
    categories = sorted(used | configured)
    return success({"brands": brands, "categories": categories})


@router.get("/parts/export")
def export_parts(db: Annotated[Session, Depends(get_db)], ids: str | None = Query(default=None, max_length=4000)):
    statement = select(Part).order_by(Part.sku)
    if ids:
        requested = [value for value in dict.fromkeys(ids.split(",")) if value][:100]
        statement = statement.where(Part.id.in_(requested))
    rows = list(db.scalars(statement))
    stream = io.StringIO(); writer = csv.writer(stream)
    writer.writerow(["SKU", "Part Number", "OEM", "Alternate Number", "Name ZH", "Name EN", "Name VI", "Brand", "Category", "Unit", "Price", "Stock", "Stock Status", "Active", "Notes"])
    for item in rows:
        writer.writerow([item.sku, item.part_no, item.oem_no or "", item.alternate_no or "", item.name_zh,
                         item.name_en or "", item.name_vi or "", item.brand, item.category or "", item.unit,
                         item.price if item.price is not None else "", item.stock, item.stock_status,
                         item.is_active, item.notes or ""])
    from fastapi.responses import Response
    return Response(content="\ufeff" + stream.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="parts.csv"'})


@router.post("/parts/bulk")
def bulk_parts(payload: PartBulkRequest, db: Annotated[Session, Depends(get_db)]) -> dict:
    rows = {item.id: item for item in db.scalars(select(Part).where(Part.id.in_(payload.ids)))}
    active = payload.action == "activate"; updated, errors = [], []
    for item_id in payload.ids:
        item = rows.get(item_id)
        if item is None:
            errors.append({"id": item_id, "message": "part not found"})
            continue
        item.is_active = active; updated.append(item_id)
    db.commit()
    return success({"updated": updated, "errors": errors, "partial_success": bool(updated) and bool(errors)})


@router.post("/parts", status_code=201)
def create_part(payload: PartCreate, db: Annotated[Session, Depends(get_db)]) -> dict:
    return success(_part_dict(db, _save(db, Part(**payload.model_dump()))))


@router.get("/parts/{part_id}")
def get_part(part_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    return success(_part_dict(db, _get_or_404(db, Part, part_id, "part")))


@router.put("/parts/{part_id}")
def update_part(part_id: str, payload: PartUpdate, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, Part, part_id, "part")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    return success(_part_dict(db, _save(db, item)))


@router.delete("/parts/{part_id}")
def deactivate_part(part_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, Part, part_id, "part")
    item.is_active = False
    _save(db, item)
    return success({"id": item.id, "is_active": False})


@router.post("/parts/{part_id}/images", status_code=201)
async def upload_part_image(
    part_id: str, db: Annotated[Session, Depends(get_db)], file: UploadFile = File(...),
    sort_order: int = Query(default=0, ge=0), image_type: str = Query(default="product", pattern="^(product|nameplate|packaging)$"),
) -> dict:
    _get_or_404(db, Part, part_id, "part")
    uploaded = await StorageService(db).upload(file, owner_key=f"admin:part:{part_id}", images_only=True)
    image = _save(db, PartImage(part_id=part_id, file_id=uploaded.id, url=uploaded.url, sort_order=sort_order,
                                image_type=image_type))
    return success(PartImageResult.model_validate(image).model_dump())


@router.put("/parts/{part_id}/images/{image_id}")
def update_part_image(part_id: str, image_id: str, payload: PartImageUpdate,
                      db: Annotated[Session, Depends(get_db)]) -> dict:
    _get_or_404(db, Part, part_id, "part")
    image = db.scalar(select(PartImage).where(PartImage.id == image_id, PartImage.part_id == part_id))
    if image is None:
        raise AppError("part image not found", code=40401, status_code=404)
    image.sort_order, image.image_type = payload.sort_order, payload.image_type
    return success(PartImageResult.model_validate(_save(db, image)).model_dump())


@router.patch("/parts/{part_id}/images/{image_id}/primary")
def primary_part_image(part_id: str, image_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    images = list(db.scalars(select(PartImage).where(PartImage.part_id == part_id).order_by(PartImage.sort_order)))
    selected = next((item for item in images if item.id == image_id), None)
    if selected is None:
        raise AppError("part image not found", code=40401, status_code=404)
    for position, image in enumerate([selected] + [item for item in images if item.id != image_id]):
        image.sort_order = position
    db.commit(); db.refresh(selected)
    return success(PartImageResult.model_validate(selected).model_dump())


@router.delete("/parts/{part_id}/images/{image_id}")
def delete_part_image(part_id: str, image_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    image = db.scalar(select(PartImage).where(PartImage.id == image_id, PartImage.part_id == part_id))
    if image is None:
        raise AppError("part image not found", code=40401, status_code=404)
    # Delete storage first: if MinIO rejects the operation, retain the image reference for a safe retry.
    StorageService(db).delete(image.file_id)
    _delete(db, image)
    return success({"id": image_id})


# Machines
def _require_machine_type(db: Session, code: str) -> None:
    if not db.scalar(select(MachineType.id).where(MachineType.code == code, MachineType.is_active.is_(True))):
        raise AppError("machine type is not configured or inactive", code=42230, status_code=422,
                       data={"field": "machine_type", "reason": "invalid_reference"})


@router.get("/machines/options")
def machine_options(db: Annotated[Session, Depends(get_db)]) -> dict:
    brands = list(db.scalars(select(Machine.brand).where(Machine.brand != "").distinct().order_by(Machine.brand)))
    types = list(db.scalars(select(MachineType).where(MachineType.is_active.is_(True)).order_by(
        MachineType.sort_order, MachineType.name, MachineType.code
    )))
    return success({"brands": brands, "types": [MachineTypeResult.model_validate(item).model_dump() for item in types]})


@router.get("/machines")
def list_machines(
    db: Annotated[Session, Depends(get_db)], brand: str | None = None,
    machine_type: str | None = None, q: str | None = None,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    statement = select(Machine).order_by(Machine.created_at.desc())
    if brand:
        statement = statement.where(Machine.brand == brand)
    if machine_type:
        statement = statement.where(Machine.machine_type == machine_type)
    if q:
        pattern = f"%{q}%"
        statement = statement.where(or_(Machine.model.ilike(pattern), Machine.series.ilike(pattern),
                                        Machine.engine_model.ilike(pattern)))
    items, total = _page(db, statement, Machine, page, page_size)
    return success(_page_data([MachineResult.model_validate(i).model_dump() for i in items], total, page, page_size))


@router.post("/machines", status_code=201)
def create_machine(payload: MachineCreate, db: Annotated[Session, Depends(get_db)]) -> dict:
    _require_machine_type(db, payload.machine_type)
    return success(MachineResult.model_validate(_save(db, Machine(**payload.model_dump()))).model_dump())


@router.get("/machines/{machine_id}")
def get_machine(machine_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    return success(MachineResult.model_validate(_get_or_404(db, Machine, machine_id, "machine")).model_dump())


@router.put("/machines/{machine_id}")
def update_machine(machine_id: str, payload: MachineUpdate, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, Machine, machine_id, "machine")
    _require_machine_type(db, payload.machine_type)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    return success(MachineResult.model_validate(_save(db, item)).model_dump())


@router.delete("/machines/{machine_id}")
def delete_machine(machine_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, Machine, machine_id, "machine")
    _delete(db, item)
    return success({"id": machine_id})


# Configurable machine types
@router.get("/machine-types")
def list_machine_types(db: Annotated[Session, Depends(get_db)]) -> dict:
    items = list(db.scalars(select(MachineType).order_by(MachineType.sort_order, MachineType.name, MachineType.code)))
    return success([MachineTypeResult.model_validate(item).model_dump() for item in items])


@router.post("/machine-types", status_code=201)
def create_machine_type(payload: MachineTypeCreate, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _save(db, MachineType(**payload.model_dump()))
    return success(MachineTypeResult.model_validate(item).model_dump())


@router.put("/machine-types/{type_id}")
def update_machine_type(type_id: str, payload: MachineTypeUpdate, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, MachineType, type_id, "machine type")
    if payload.code != item.code and db.scalar(select(Machine.id).where(Machine.machine_type == item.code).limit(1)):
        raise AppError("machine type code is in use", code=42231, status_code=422,
                       data={"field": "code", "reason": "in_use"})
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    return success(MachineTypeResult.model_validate(_save(db, item)).model_dump())


@router.delete("/machine-types/{type_id}")
def delete_machine_type(type_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, MachineType, type_id, "machine type")
    if db.scalar(select(Machine.id).where(Machine.machine_type == item.code).limit(1)):
        raise AppError("machine type is used by machines", code=42231, status_code=422,
                       data={"field": "code", "reason": "in_use"})
    _delete(db, item)
    return success({"id": type_id})


# Machine-part relations
def _machine_part_dict(db: Session, item: MachinePartRelation) -> dict[str, Any]:
    data = MachinePartResult.model_validate(item).model_dump()
    part = db.get(Part, item.part_id)
    if part:
        data.update({"part_no": part.part_no, "part_name": part.name_zh or part.name_en,
                     "part_brand": part.brand, "part_category": part.category})
    return data


@router.get("/relations/machine-part")
def list_machine_parts(
    db: Annotated[Session, Depends(get_db)], machine_id: str | None = None, part_id: str | None = None,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    statement = select(MachinePartRelation).order_by(MachinePartRelation.priority.desc(), MachinePartRelation.created_at.desc())
    if machine_id:
        statement = statement.where(MachinePartRelation.machine_id == machine_id)
    if part_id:
        statement = statement.where(MachinePartRelation.part_id == part_id)
    items, total = _page(db, statement, MachinePartRelation, page, page_size)
    return success(_page_data([_machine_part_dict(db, i) for i in items], total, page, page_size))


@router.post("/relations/machine-part", status_code=201)
def create_machine_part(payload: MachinePartCreate, db: Annotated[Session, Depends(get_db)]) -> dict:
    return success(_machine_part_dict(db, _save(db, MachinePartRelation(**payload.model_dump()))))


@router.get("/relations/machine-part/{relation_id}")
def get_machine_part(relation_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, MachinePartRelation, relation_id, "machine-part relation")
    return success(_machine_part_dict(db, item))


@router.put("/relations/machine-part/{relation_id}")
def update_machine_part(relation_id: str, payload: MachinePartUpdate, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, MachinePartRelation, relation_id, "machine-part relation")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    return success(_machine_part_dict(db, _save(db, item)))


@router.delete("/relations/machine-part/{relation_id}")
def delete_machine_part(relation_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    _delete(db, _get_or_404(db, MachinePartRelation, relation_id, "machine-part relation"))
    return success({"id": relation_id})


@router.post("/relations/machine-part/import", status_code=201)
async def import_machine_parts(
    db: Annotated[Session, Depends(get_db)], file: UploadFile = File(...),
    machine_id: str | None = Query(default=None, max_length=36), dry_run: bool = False,
) -> dict:
    if not (file.filename or "").lower().endswith(".csv"):
        raise AppError("file must be CSV", code=42210, status_code=422, data={"field": "file"})
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise AppError("CSV is too large", code=42211, status_code=422, data={"field": "file"})
    try:
        rows = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    except UnicodeDecodeError as error:
        raise AppError("CSV must be UTF-8", code=42212, status_code=422, data={"field": "file"}) from error
    required = {"part_id"} | (set() if machine_id else {"machine_id"})
    if not rows.fieldnames or not required.issubset(rows.fieldnames):
        raise AppError("CSV requires part_id and machine_id columns unless machine_id is supplied", code=42213, status_code=422, data={"field": "file"})
    created, valid, processed, errors, seen = 0, 0, 0, [], set()
    for line, row in enumerate(rows, 2):
        processed += 1
        if processed > 1000:
            errors.append({"line": line, "message": "CSV supports at most 1000 data rows", "reason": "too_many_rows"})
            break
        try:
            payload = MachinePartCreate.model_validate({
                "machine_id": machine_id or row.get("machine_id"), "part_id": row.get("part_id"),
                "system": row.get("system") or None, "position": row.get("position") or None,
                "serial_from": row.get("serial_from") or None, "serial_to": row.get("serial_to") or None,
                "notes": row.get("notes") or None, "priority": row.get("priority") or 0,
                "is_active": row.get("is_active") or True,
            })
            if db.get(Machine, payload.machine_id) is None:
                raise AppError("machine not found", code=42202, status_code=422,
                               data={"field": "machine_id", "reason": "invalid_foreign_key"})
            if db.get(Part, payload.part_id) is None:
                raise AppError("part not found", code=42202, status_code=422,
                               data={"field": "part_id", "reason": "invalid_foreign_key"})
            key = (payload.machine_id, payload.part_id)
            if key in seen or db.scalar(select(MachinePartRelation.id).where(
                MachinePartRelation.machine_id == payload.machine_id,
                MachinePartRelation.part_id == payload.part_id,
            )):
                raise AppError("machine-part relation already exists", code=42201, status_code=422,
                               data={"field": "part_id", "reason": "not_unique"})
            seen.add(key); valid += 1
            if not dry_run:
                _save(db, MachinePartRelation(**payload.model_dump())); created += 1
        except Exception as error:
            db.rollback()
            reason = error.data.get("reason") if isinstance(error, AppError) else "invalid_row"
            errors.append({"line": line, "message": getattr(error, "message", str(error)), "reason": reason})
    return success(CsvImportResult(created=created, valid=valid, processed=processed,
                                   dry_run=dry_run, errors=errors).model_dump())


# Cross references
def _part_summary(item: Part | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "id": item.id, "part_no": item.part_no, "brand": item.brand,
        "name": item.name_zh or item.name_en or item.name_vi, "is_active": item.is_active,
    }


def _cross_ref_dict(db: Session, item: PartCrossReference) -> dict[str, Any]:
    data = CrossRefResult.model_validate(item).model_dump()
    source_part, target_part = db.get(Part, item.source_part_id), db.get(Part, item.target_part_id)
    data["source_part"] = _part_summary(source_part)
    data["target_part"] = _part_summary(target_part)
    data["source_part_no"] = source_part.part_no if source_part else None
    data["target_part_no"] = target_part.part_no if target_part else None
    data["direction"] = "source_to_target"
    reliability = float(item.reliability)
    data["quality"] = "high" if reliability >= .85 else "medium" if reliability >= .65 else "low"
    return data


def _lock_cross_ref_graph(db: Session) -> None:
    """Serialize graph mutations so two concurrent writes cannot bypass cycle checks."""
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(18003301)"))
    else:
        db.execute(select(PartCrossReference.id).with_for_update())


def _cross_ref_conflicts(
    db: Session, source_id: str, target_id: str, exclude_id: str | None = None,
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    if source_id == target_id:
        return [{
            "type": "self_reference", "message": "原件与替代件不能是同一个配件",
            "action": {"kind": "change_target", "label": "更换替代件"},
        }]

    parts = {item.id: item for item in db.scalars(select(Part).where(Part.id.in_([source_id, target_id])))}
    for role, part_id in (("source_part_id", source_id), ("target_part_id", target_id)):
        part = parts.get(part_id)
        if part is None:
            conflicts.append({
                "type": "missing_part", "message": f"{role} 对应的配件不存在", "field": role,
                "action": {"kind": "choose_part", "label": "重新选择配件"},
            })
        elif not part.is_active:
            conflicts.append({
                "type": "inactive_part", "message": f"{part.part_no} 已停用，不能建立引用关系", "field": role,
                "action": {"kind": "choose_part", "label": "选择启用的配件"},
            })
    if conflicts:
        return conflicts

    statement = select(PartCrossReference).where(or_(
        and_(PartCrossReference.source_part_id == source_id, PartCrossReference.target_part_id == target_id),
        and_(PartCrossReference.source_part_id == target_id, PartCrossReference.target_part_id == source_id),
    ))
    if exclude_id:
        statement = statement.where(PartCrossReference.id != exclude_id)
    existing = db.scalar(statement)
    if existing:
        reverse = existing.source_part_id == target_id
        conflicts.append({
            "type": "reverse_duplicate" if reverse else "duplicate",
            "message": "反向关系已存在" if reverse else "同向关系已存在",
            "relation_id": existing.id,
            "action": {"kind": "edit_existing", "label": "编辑现有关系", "relation_id": existing.id},
        })
        return conflicts

    graph_statement = select(
        PartCrossReference.source_part_id, PartCrossReference.target_part_id,
    ).where(PartCrossReference.status.in_(["active", "pending"]))
    if exclude_id:
        graph_statement = graph_statement.where(PartCrossReference.id != exclude_id)
    adjacency: dict[str, list[str]] = {}
    for row_source, row_target in db.execute(graph_statement):
        adjacency.setdefault(row_source, []).append(row_target)

    queue: list[list[str]] = [[target_id]]
    visited = {target_id}
    cycle_path: list[str] | None = None
    while queue:
        path = queue.pop(0)
        for next_id in adjacency.get(path[-1], []):
            if next_id == source_id:
                cycle_path = [source_id, *path, source_id]
                queue.clear()
                break
            if next_id not in visited:
                visited.add(next_id)
                queue.append([*path, next_id])
        if cycle_path:
            break
    if cycle_path:
        numbers = {item.id: item.part_no for item in db.scalars(select(Part).where(Part.id.in_(cycle_path)))}
        conflicts.append({
            "type": "cycle", "message": "该关系会形成循环引用",
            "path": [{"id": item_id, "part_no": numbers.get(item_id, item_id)} for item_id in cycle_path],
            "action": {"kind": "change_target", "label": "更换替代件"},
        })
    return conflicts


def _raise_cross_ref_conflict(conflicts: list[dict[str, Any]]) -> None:
    if not conflicts:
        return
    duplicate = any(item["type"] in {"duplicate", "reverse_duplicate"} for item in conflicts)
    message = "cross-reference already exists in either direction" if duplicate else conflicts[0]["message"]
    raise AppError(message, code=42220, status_code=422, data={
        "field": "source_part_id,target_part_id", "reason": conflicts[0]["type"], "conflicts": conflicts,
    })


@router.get("/cross-refs")
def list_cross_refs(
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(default=None, max_length=150),
    part_number: str | None = Query(default=None, max_length=150),
    relation_type: str | None = Query(default=None, max_length=30),
    status: str | None = Query(default=None, pattern="^(pending|active|inactive|rejected)$"),
    part_id: str | None = Query(default=None, max_length=36),
    direction: str = Query(default="all", pattern="^(all|source|target)$"),
    sort_by: str = Query(default="priority", pattern="^(created_at|reliability|priority|status)$"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    sort_column = getattr(PartCrossReference, sort_by)
    statement = select(PartCrossReference).order_by(
        (asc if sort_dir == "asc" else desc)(sort_column), PartCrossReference.created_at.desc(),
    )
    keyword = (q or part_number or "").strip()
    if keyword:
        pattern = f"%{keyword}%"
        ids = select(Part.id).where(or_(Part.part_no.ilike(pattern), Part.brand.ilike(pattern),
                                             Part.name_zh.ilike(pattern), Part.name_en.ilike(pattern)))
        statement = statement.where(or_(PartCrossReference.source_part_id.in_(ids), PartCrossReference.target_part_id.in_(ids)))
    if relation_type:
        statement = statement.where(PartCrossReference.relation_type == relation_type)
    if status:
        statement = statement.where(PartCrossReference.status == status)
    if part_id:
        if direction == "source":
            statement = statement.where(PartCrossReference.source_part_id == part_id)
        elif direction == "target":
            statement = statement.where(PartCrossReference.target_part_id == part_id)
        else:
            statement = statement.where(or_(PartCrossReference.source_part_id == part_id,
                                            PartCrossReference.target_part_id == part_id))
    items, total = _page(db, statement, PartCrossReference, page, page_size)
    return success(_page_data([_cross_ref_dict(db, i) for i in items], total, page, page_size))


@router.get("/cross-refs/conflicts")
def check_cross_ref_conflicts(
    db: Annotated[Session, Depends(get_db)],
    source_part_id: str = Query(max_length=36), target_part_id: str = Query(max_length=36),
    exclude_id: str | None = Query(default=None, max_length=36),
) -> dict:
    conflicts = _cross_ref_conflicts(db, source_part_id, target_part_id, exclude_id)
    return success({"can_save": not conflicts, "conflicts": conflicts})


@router.post("/cross-refs", status_code=201)
def create_cross_ref(payload: CrossRefCreate, db: Annotated[Session, Depends(get_db)]) -> dict:
    _lock_cross_ref_graph(db)
    _raise_cross_ref_conflict(_cross_ref_conflicts(db, payload.source_part_id, payload.target_part_id))
    return success(_cross_ref_dict(db, _save(db, PartCrossReference(**payload.model_dump()))))


@router.get("/cross-refs/{cross_ref_id}")
def get_cross_ref(cross_ref_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    return success(_cross_ref_dict(db, _get_or_404(db, PartCrossReference, cross_ref_id, "cross-reference")))


@router.put("/cross-refs/{cross_ref_id}")
def update_cross_ref(cross_ref_id: str, payload: CrossRefUpdate, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, PartCrossReference, cross_ref_id, "cross-reference")
    _lock_cross_ref_graph(db)
    _raise_cross_ref_conflict(_cross_ref_conflicts(db, payload.source_part_id, payload.target_part_id, cross_ref_id))
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    return success(_cross_ref_dict(db, _save(db, item)))


@router.delete("/cross-refs/{cross_ref_id}")
def delete_cross_ref(cross_ref_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    _delete(db, _get_or_404(db, PartCrossReference, cross_ref_id, "cross-reference"))
    return success({"id": cross_ref_id})


# Aliases
def _alias_conflict(db: Session, part_id: str, alias: str, language: str,
                    exclude_id: str | None = None) -> None:
    statement = select(PartAlias.id).where(
        PartAlias.part_id == part_id,
        func.lower(PartAlias.alias) == alias.strip().lower(),
        func.lower(PartAlias.language) == language.strip().lower(),
    )
    if exclude_id:
        statement = statement.where(PartAlias.id != exclude_id)
    if db.scalar(statement):
        raise AppError("alias already exists for this language", code=42201, status_code=422,
                       data={"field": "alias", "reason": "not_unique"})


@router.get("/aliases")
def list_aliases(
    db: Annotated[Session, Depends(get_db)], part_id: str | None = None, status: str | None = None,
    q: str | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    statement = select(PartAlias).order_by(PartAlias.created_at.desc())
    if part_id:
        statement = statement.where(PartAlias.part_id == part_id)
    if status:
        statement = statement.where(PartAlias.status == status)
    if q:
        statement = statement.where(PartAlias.alias.ilike(f"%{q}%"))
    items, total = _page(db, statement, PartAlias, page, page_size)
    return success(_page_data([AliasResult.model_validate(i).model_dump() for i in items], total, page, page_size))


@router.post("/aliases", status_code=201)
def create_alias(payload: AliasCreate, db: Annotated[Session, Depends(get_db)]) -> dict:
    _alias_conflict(db, payload.part_id, payload.alias, payload.language)
    return success(AliasResult.model_validate(_save(db, PartAlias(**payload.model_dump()))).model_dump())


@router.get("/aliases/{alias_id}")
def get_alias(alias_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    return success(AliasResult.model_validate(_get_or_404(db, PartAlias, alias_id, "alias")).model_dump())


@router.put("/aliases/{alias_id}")
def update_alias(alias_id: str, payload: AliasUpdate, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, PartAlias, alias_id, "alias")
    _alias_conflict(db, payload.part_id, payload.alias, payload.language, alias_id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    return success(AliasResult.model_validate(_save(db, item)).model_dump())


@router.patch("/aliases/{alias_id}/status")
def update_alias_status(alias_id: str, payload: AliasStatusUpdate, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, PartAlias, alias_id, "alias")
    if item.status != "pending":
        raise AppError("only pending aliases can be reviewed", code=42230, status_code=422,
                       data={"field": "status", "reason": "invalid_transition"})
    item.status = payload.status
    return success(AliasResult.model_validate(_save(db, item)).model_dump())


@router.delete("/aliases/{alias_id}")
def delete_alias(alias_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    _delete(db, _get_or_404(db, PartAlias, alias_id, "alias"))
    return success({"id": alias_id})


# Categories
@router.get("/categories")
def list_categories(
    db: Annotated[Session, Depends(get_db)], parent_id: str | None = None, is_active: bool | None = None,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=100, ge=1, le=100),
) -> dict:
    statement = select(PartCategory).order_by(PartCategory.sort_order, PartCategory.name)
    if parent_id:
        statement = statement.where(PartCategory.parent_id == parent_id)
    if is_active is not None:
        statement = statement.where(PartCategory.is_active == is_active)
    items, total = _page(db, statement, PartCategory, page, page_size)
    return success(_page_data([CategoryResult.model_validate(i).model_dump() for i in items], total, page, page_size))


def _validate_parent(db: Session, parent_id: str | None, item_id: str | None = None) -> None:
    if not parent_id:
        return
    parent = _get_or_404(db, PartCategory, parent_id, "parent category")
    if parent.parent_id is not None:
        raise AppError("categories support at most two levels", code=42240, status_code=422,
                       data={"field": "parent_id", "reason": "max_depth"})
    if item_id and parent.id == item_id:
        raise AppError("category cannot be its own parent", code=42241, status_code=422,
                       data={"field": "parent_id", "reason": "cycle"})


@router.post("/categories", status_code=201)
def create_category(payload: CategoryCreate, db: Annotated[Session, Depends(get_db)]) -> dict:
    _validate_parent(db, payload.parent_id)
    return success(CategoryResult.model_validate(_save(db, PartCategory(**payload.model_dump()))).model_dump())


@router.get("/categories/{category_id}")
def get_category(category_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    return success(CategoryResult.model_validate(_get_or_404(db, PartCategory, category_id, "category")).model_dump())


@router.put("/categories/{category_id}")
def update_category(category_id: str, payload: CategoryUpdate, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, PartCategory, category_id, "category")
    _validate_parent(db, payload.parent_id, category_id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    return success(CategoryResult.model_validate(_save(db, item)).model_dump())


@router.delete("/categories/{category_id}")
def delete_category(category_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    item = _get_or_404(db, PartCategory, category_id, "category")
    item.is_active = False
    _save(db, item)
    return success({"id": category_id, "is_active": False})
