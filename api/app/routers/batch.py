from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.responses import success
from app.models import ExcelBatch, ExcelBatchJob, ExcelBatchRow, PartQueryLog
from app.routers.cart import get_cart_owner
from app.schemas.batch import BatchCartRequest, BatchRowUpdate, BatchTicketRequest
from app.services.cart import CartOwner
from app.services.config_service import ConfigService
from app.services.excel_batch import (ExcelBatchService, create_template, parse_excel, run_match_job,
                                      validate_excel_file)
from app.services.storage import StorageService
from app.services.catalog_validation import normalize_part_number

router = APIRouter(prefix="/api/v1/batch", tags=["Excel Batch"])


@router.get("/template")
def template(db: Annotated[Session, Depends(get_db)],
             lang: Literal["zh", "en", "vi"] = "zh") -> StreamingResponse:
    configured = ConfigService(db).get("batch.template_examples", {})
    example = configured.get(lang) if isinstance(configured, dict) else None
    # Retain compatibility with the original Chinese example configuration.
    if example is None and lang == "zh":
        example = ConfigService(db).get("batch.template_example", None)
    content = create_template(example, lang=lang)
    headers = {"Content-Disposition": f'attachment; filename="partsmatch-batch-template-{lang}.xlsx"',
               "X-Content-Type-Options": "nosniff"}
    return StreamingResponse(BytesIO(content), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers=headers)


@router.post("/upload", status_code=201)
async def upload_batch(
    file: Annotated[UploadFile, File()], db: Annotated[Session, Depends(get_db)],
    owner: Annotated[CartOwner, Depends(get_cart_owner)],
) -> dict:
    configs = ConfigService(db)
    configured_limit = int(configs.get("batch.max_file_bytes", 5 * 1024 * 1024))
    content = await file.read(min(max(configured_limit, 1), 5 * 1024 * 1024) + 1)
    name = Path(file.filename or "upload").name
    extension = validate_excel_file(name, file.content_type, content, configs)
    max_rows = min(int(configs.get("batch.max_rows", 500)), 500)
    parsed, errors = parse_excel(extension, content, max_rows)
    if not parsed:
        raise AppError("Excel has no data rows", code="EMPTY_EXCEL", status_code=400)

    await file.seek(0)
    record = await StorageService(db).upload(file, owner_key=owner.owner_key)
    groups: dict[tuple[str, int], list[int]] = {}
    for item in parsed:
        raw_part_no = item["normalized"].get("part_no") or ""
        part_no = normalize_part_number(raw_part_no).casefold() if raw_part_no else ""
        if part_no and item["quantity"]:
            groups.setdefault((part_no, item["quantity"]), []).append(item["row_index"])
    duplicates = [{"part_number": part_no, "quantity": quantity, "row_indexes": indexes,
                   "suggestion": "merge"} for (part_no, quantity), indexes in groups.items() if len(indexes) > 1]
    batch = ExcelBatch(owner_key=owner.owner_key, session_id=owner.session_id, user_id=owner.user_id,
                       file_id=record.id, original_name=name, total_rows=len(parsed),
                       valid_rows=sum(not item["errors"] for item in parsed), status="uploaded",
                       duplicate_rows=duplicates)
    db.add(batch)
    db.flush()
    db.add(PartQueryLog(
        session_id=owner.session_id, user_id=owner.user_id, query_type="excel", source_id=batch.id,
        query_text=name, request_data={"batch_id": batch.id, "file_id": record.id},
        raw_input={"file_id": record.id, "original_name": name}, extracted_info={"total_rows": len(parsed)},
        ai_result=None, result_count=0, match_status="insufficient" if errors else None,
        need_manual=bool(errors),
    ))
    db.add_all([ExcelBatchRow(batch_id=batch.id, row_index=item["row_index"], raw_content=item["raw"],
                              normalized_content=item["normalized"], quantity=item["quantity"],
                              validation_errors=item["errors"]) for item in parsed])
    db.commit()
    return success({"batch_id": batch.id, "file_id": record.id, "total_rows": batch.total_rows,
                    "valid_rows": batch.valid_rows, "validation_errors": errors, "duplicate_rows": duplicates})


@router.get("/{batch_id}")
def get_batch(batch_id: str, db: Annotated[Session, Depends(get_db)],
              owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    service = ExcelBatchService(db, owner)
    batch = service.owned(batch_id)
    return success({"batch_id": batch.id, "file_id": batch.file_id, "original_name": batch.original_name,
                    "status": batch.status, "total_rows": batch.total_rows, "valid_rows": batch.valid_rows,
                    "duplicate_rows": batch.duplicate_rows or [],
                    "rows": [service.serialize_row(row) for row in service.rows(batch.id)]})


@router.get("/{batch_id}/status")
def get_batch_status(batch_id: str, db: Annotated[Session, Depends(get_db)],
                     owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    service = ExcelBatchService(db, owner)
    batch = service.owned(batch_id)
    job = db.scalar(select(ExcelBatchJob).where(
        ExcelBatchJob.batch_id == batch.id, ExcelBatchJob.owner_key == owner.owner_key
    ).order_by(ExcelBatchJob.created_at.desc()))
    if job:
        return success(_job_payload(job))
    return success({"job_id": "", "batch_id": batch.id, "status": batch.status, "attempts": 0,
                    "processed_rows": batch.valid_rows if batch.status == "matched" else 0,
                    "total_rows": batch.valid_rows, "error": None, "started_at": None, "finished_at": None})


@router.patch("/{batch_id}/rows/{row_index}")
def update_batch_row(batch_id: str, row_index: int, payload: BatchRowUpdate,
                     db: Annotated[Session, Depends(get_db)],
                     owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    service = ExcelBatchService(db, owner)
    batch = service.owned(batch_id, lock=True)
    return success(service.update_row(batch, row_index, payload))


@router.post("/{batch_id}/match")
def match_batch(batch_id: str, background_tasks: BackgroundTasks, db: Annotated[Session, Depends(get_db)],
                owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    service = ExcelBatchService(db, owner)
    batch = service.owned(batch_id, lock=True)
    if not batch.valid_rows:
        raise AppError("batch has no valid rows", code="BATCH_NO_VALID_ROWS", status_code=409)
    threshold = min(max(int(ConfigService(db).get("batch.async_threshold", 50)), 1), 50)
    if batch.valid_rows <= threshold:
        return success({"mode": "sync", "batch_id": batch.id, "status": "completed",
                        "rows": service.match_all(batch), "duplicate_rows": batch.duplicate_rows or []})
    active = db.scalar(select(ExcelBatchJob).where(ExcelBatchJob.batch_id == batch.id,
                                                   ExcelBatchJob.status.in_(["queued", "running", "retrying"])))
    if active is None:
        active = ExcelBatchJob(batch_id=batch.id, owner_key=owner.owner_key, status="queued",
                               total_rows=batch.valid_rows, processed_rows=0)
        db.add(active)
        batch.status = "queued"
        db.commit()
    background_tasks.add_task(run_match_job, db.get_bind(), active.id)
    return success({"mode": "async", "batch_id": batch.id, "job_id": active.id, "status": active.status,
                    "poll_url": f"/api/v1/batch/jobs/{active.id}"})


def _job_payload(job: ExcelBatchJob) -> dict:
    return {"job_id": job.id, "batch_id": job.batch_id, "status": job.status, "attempts": job.attempts,
            "processed_rows": job.processed_rows, "total_rows": job.total_rows, "error": job.error,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Annotated[Session, Depends(get_db)],
            owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    job = db.scalar(select(ExcelBatchJob).where(ExcelBatchJob.id == job_id,
                                                ExcelBatchJob.owner_key == owner.owner_key))
    if job is None:
        raise AppError("batch job not found", code="BATCH_JOB_NOT_FOUND", status_code=404)
    return success(_job_payload(job))


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, background_tasks: BackgroundTasks, db: Annotated[Session, Depends(get_db)],
              owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    job = db.scalar(select(ExcelBatchJob).where(ExcelBatchJob.id == job_id,
                                                ExcelBatchJob.owner_key == owner.owner_key).with_for_update())
    if job is None:
        raise AppError("batch job not found", code="BATCH_JOB_NOT_FOUND", status_code=404)
    max_attempts = min(max(int(ConfigService(db).get("batch.max_job_attempts", 3)), 1), 10)
    if job.status != "failed":
        raise AppError("only failed jobs can be retried", code="BATCH_JOB_NOT_FAILED", status_code=409)
    if job.attempts >= max_attempts:
        raise AppError("job retry limit reached", code="BATCH_JOB_RETRY_LIMIT", status_code=409)
    job.status, job.processed_rows, job.error, job.finished_at = "retrying", 0, None, None
    db.commit()
    background_tasks.add_task(run_match_job, db.get_bind(), job.id)
    return success(_job_payload(job))


@router.post("/{batch_id}/add-to-cart")
def add_to_cart(batch_id: str, payload: BatchCartRequest, db: Annotated[Session, Depends(get_db)],
                owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    service = ExcelBatchService(db, owner)
    batch = service.owned(batch_id)
    return success(service.add_to_cart(batch, payload))


@router.post("/{batch_id}/create-tickets")
def create_tickets(batch_id: str, payload: BatchTicketRequest, db: Annotated[Session, Depends(get_db)],
                   owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    service = ExcelBatchService(db, owner)
    batch = service.owned(batch_id)
    return success(service.create_tickets(batch, payload))
