from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.responses import success
from app.core.security import require_role
from app.models import (AdminUser, AiMatchEvidence, CartItem, FileObject, KnowledgeCandidate, LlmCallLog,
                        ManualTicketPart, Part, PartQueryLog, QueryLogCorrection)
from app.schemas.ai_matching import (QueryLogCorrectionCreate, QueryLogDetail, QueryLogListItem,
                                     QueryLogPage)

router = APIRouter(prefix="/api/v1/admin/query-logs", tags=["Admin query logs"])

_SECRET_KEYS = ("password", "passwd", "token", "secret", "api_key", "apikey", "authorization", "cookie")
_CONTACT_KEYS = ("contact", "email", "phone", "mobile", "wechat", "whatsapp", "telegram", "zalo")
_EMAIL = re.compile(r"(?<![\w.-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")


def _source(query_type: str) -> Literal["text", "image", "excel", "manual"]:
    if query_type == "image":
        return "image"
    if query_type in {"excel", "batch"}:
        return "excel"
    if query_type == "manual":
        return "manual"
    return "text"


def _redact(value: Any, key: str = "") -> Any:
    lowered = key.casefold()
    if any(item in lowered for item in _SECRET_KEYS + _CONTACT_KEYS):
        return "[REDACTED]" if value not in (None, "") else value
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _BEARER.sub("Bearer [REDACTED]", _PHONE.sub("[REDACTED_PHONE]", _EMAIL.sub("[REDACTED_EMAIL]", value)))
    return value


def _summary(item: PartQueryLog) -> QueryLogListItem:
    return QueryLogListItem(
        id=item.id, session_id=item.session_id, user_id=item.user_id, query_type=item.query_type,
        source=_source(item.query_type), source_id=item.source_id, query_text=_redact(item.query_text),
        result_count=item.result_count, confidence=float(item.confidence) if item.confidence is not None else None,
        match_status=item.match_status, need_manual=item.need_manual, duration_ms=item.duration_ms,
        created_at=item.created_at,
    )


def _part(part: Part) -> dict[str, Any]:
    return {"id": part.id, "part_no": part.part_no, "brand": part.brand, "name_zh": part.name_zh,
            "name_en": part.name_en}


def _correction(db: Session, item: QueryLogCorrection | None) -> dict[str, Any] | None:
    if item is None:
        return None
    actor = db.get(AdminUser, item.actor_id) if item.actor_id else None
    recommended = db.get(Part, item.recommended_part_id) if item.recommended_part_id else None
    correct = db.get(Part, item.correct_part_id)
    return {"id": item.id, "status": item.status, "reason": _redact(item.reason),
            "actor": {"id": actor.id, "username": actor.username} if actor else None,
            "recommended_part": _part(recommended) if recommended else None,
            "correct_part": _part(correct) if correct else None, "created_at": item.created_at}


def _file_ids(item: PartQueryLog) -> set[str]:
    ids: set[str] = set()
    for payload in (item.request_data, item.raw_input):
        if not isinstance(payload, dict):
            continue
        for key in ("file_id", "image_id"):
            if isinstance(payload.get(key), str):
                ids.add(payload[key])
        for key in ("file_ids", "image_ids"):
            if isinstance(payload.get(key), list):
                ids.update(value for value in payload[key] if isinstance(value, str))
    return ids


@router.get("")
def list_query_logs(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role("admin", "operator"))],
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    date_from: datetime | None = None, date_to: datetime | None = None,
    source: Literal["text", "image", "excel", "manual"] | None = None,
    query_type: str | None = Query(default=None, max_length=30),
    status: Literal["exact", "high", "low", "multiple", "insufficient", "not_found"] | None = None,
    q: str | None = Query(default=None, max_length=200),
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise AppError("date_from must not be after date_to", code=40030, status_code=400)
    filters = []
    if date_from:
        filters.append(PartQueryLog.created_at >= date_from)
    if date_to:
        filters.append(PartQueryLog.created_at <= date_to)
    if query_type:
        filters.append(PartQueryLog.query_type == query_type)
    elif source == "image":
        filters.append(PartQueryLog.query_type == "image")
    elif source == "excel":
        filters.append(PartQueryLog.query_type.in_(("excel", "batch")))
    elif source == "manual":
        filters.append(PartQueryLog.query_type == "manual")
    elif source == "text":
        filters.append(PartQueryLog.query_type.not_in(("image", "excel", "batch", "manual")))
    if status:
        filters.append(PartQueryLog.match_status == status)
    if q and q.strip():
        filters.append(PartQueryLog.query_text.ilike(f"%{q.strip()}%"))
    total = db.scalar(select(func.count()).select_from(PartQueryLog).where(*filters)) or 0
    rows = list(db.scalars(select(PartQueryLog).where(*filters).order_by(
        PartQueryLog.created_at.desc(), PartQueryLog.id.desc(),
    ).offset((page - 1) * page_size).limit(page_size)))
    result = QueryLogPage(items=[_summary(item) for item in rows], page=page, page_size=page_size, total=total)
    return success(result.model_dump(mode="json"))


@router.get("/stats")
def query_log_stats(db: Annotated[Session, Depends(get_db)],
                    _: Annotated[AdminUser, Depends(require_role("admin", "operator"))]) -> dict:
    now = datetime.now(UTC)
    start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    total, exact, manual = db.execute(select(
        func.count(),
        func.count().filter(PartQueryLog.match_status == "exact"),
        func.count().filter(PartQueryLog.need_manual.is_(True)),
    ).where(PartQueryLog.created_at >= start, PartQueryLog.created_at < end)).one()
    total = int(total or 0); exact = int(exact or 0); manual = int(manual or 0)
    return success({"period": "utc_today", "query_count": total, "exact_count": exact,
                    "manual_count": manual, "exact_rate": exact / total if total else 0,
                    "manual_rate": manual / total if total else 0})


@router.get("/{query_log_id}")
def query_log_detail(
    query_log_id: str, db: Annotated[Session, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role("admin", "operator"))],
) -> dict:
    item = db.get(PartQueryLog, query_log_id)
    if item is None:
        raise AppError("query log not found", code=40431, status_code=404)
    evidence_rows = list(db.execute(select(AiMatchEvidence, Part).join(
        Part, Part.id == AiMatchEvidence.part_id).where(AiMatchEvidence.query_log_id == item.id).order_by(
        AiMatchEvidence.confidence.desc(), AiMatchEvidence.id)))
    evidence = [{"id": row.id, "part_id": row.part_id, "confidence": float(row.confidence),
                 "reason": _redact(row.reason), "evidence": _redact(row.evidence)} for row, _ in evidence_rows]
    candidates = [{**_part(part), "confidence": float(row.confidence), "reason": _redact(row.reason)}
                  for row, part in evidence_rows]
    files = list(db.scalars(select(FileObject).where(FileObject.id.in_(_file_ids(item))))) if _file_ids(item) else []
    uploaded = [{"id": file.id, "original_name": _redact(file.original_name), "mime_type": file.mime_type,
                 "size": file.size, "url": urlunsplit(urlsplit(file.url)._replace(query="", fragment=""))}
                for file in files]
    llm = list(db.scalars(select(LlmCallLog).where(LlmCallLog.query_log_id == item.id).order_by(
        LlmCallLog.created_at, LlmCallLog.id)))
    calls = [{"id": call.id, "provider": call.provider, "api_mode": call.api_mode, "model": call.model,
              "input_tokens": call.input_tokens, "output_tokens": call.output_tokens,
              "duration_ms": call.duration_ms, "status": call.status, "error_type": call.error_type,
              "error_message": _redact(call.error_message), "created_at": call.created_at} for call in llm]
    selected_rows = list(db.execute(select(CartItem, Part).join(Part, Part.id == CartItem.part_id).where(
        CartItem.query_id == item.id).order_by(CartItem.created_at)))
    selected = [{**_part(part), "quantity": cart.quantity, "source": cart.source,
                 "selected_at": cart.created_at} for cart, part in selected_rows]
    if item.query_type == "manual" and item.source_id:
        manual_rows = list(db.execute(select(ManualTicketPart, Part).join(
            Part, Part.id == ManualTicketPart.part_id).where(ManualTicketPart.ticket_id == item.source_id)))
        known = {part["id"] for part in selected}
        selected.extend({**_part(part), "quantity": row.quantity, "source": "manual_resolution",
                         "selected_at": row.created_at} for row, part in manual_rows if part.id not in known)
    correction = db.scalar(select(QueryLogCorrection).where(QueryLogCorrection.query_log_id == item.id))
    base = _summary(item).model_dump()
    detail = QueryLogDetail(
        **base, client_ip="[REDACTED]" if item.client_ip else None,
        request_data=_redact(item.request_data or {}), raw_input=_redact(item.raw_input),
        extracted_info=_redact(item.extracted_info), ai_result=_redact(item.ai_result), evidence=evidence,
        candidates=candidates, uploaded_files=uploaded, llm_calls=calls, selected_parts=selected,
        correction=_correction(db, correction),
    )
    return success(detail.model_dump(mode="json"))


@router.post("/{query_log_id}/corrections", status_code=201)
def correct_query_log(
    query_log_id: str, payload: QueryLogCorrectionCreate, db: Annotated[Session, Depends(get_db)],
    actor: Annotated[AdminUser, Depends(require_role("admin"))],
) -> dict:
    item = db.scalar(select(PartQueryLog).where(PartQueryLog.id == query_log_id).with_for_update())
    if item is None:
        raise AppError("query log not found", code=40431, status_code=404)
    existing = db.scalar(select(QueryLogCorrection).where(QueryLogCorrection.query_log_id == item.id))
    if existing is not None:
        raise AppError("query log already has a correction", code=40941, status_code=409)
    correct = db.scalar(select(Part).where(Part.id == payload.correct_part_id, Part.is_active.is_(True)))
    if correct is None:
        raise AppError("correct part must exist and be active", code=40433, status_code=404)
    if payload.recommended_part_id:
        if payload.recommended_part_id == payload.correct_part_id:
            raise AppError("recommended and correct part must differ", code=42241, status_code=422)
        recommendation = db.scalar(select(AiMatchEvidence).where(
            AiMatchEvidence.query_log_id == item.id, AiMatchEvidence.part_id == payload.recommended_part_id))
        if recommendation is None:
            raise AppError("recommended part is not in this query evidence", code=42242, status_code=422)
    correction = QueryLogCorrection(query_log_id=item.id, recommended_part_id=payload.recommended_part_id,
                                    correct_part_id=correct.id, actor_id=actor.id, reason=payload.reason,
                                    status="pending_review")
    db.add(correction)
    try:
        db.flush()
        db.add(KnowledgeCandidate(ticket_id=None, query_correction_id=correction.id, status="pending_review", payload={
            "source": {"type": "query_log_correction", "query_log_id": item.id, "correction_id": correction.id},
            "query": {"type": item.query_type, "text": _redact(item.query_text),
                      "extracted_info": _redact(item.extracted_info)},
            "recommended_part_id": payload.recommended_part_id, "correct_part_id": correct.id,
            "reason": _redact(payload.reason),
        }))
        db.commit(); db.refresh(correction)
    except IntegrityError as exc:
        db.rollback()
        raise AppError("query log already has a correction", code=40941, status_code=409) from exc
    return success(_correction(db, correction))
