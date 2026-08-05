from __future__ import annotations

import logging
import ipaddress
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.responses import success
from app.models import Machine, Part
from app.schemas.search import SearchRequest, SearchResult
from app.services.cache import CacheService, get_cache
from app.services.part_search import PartSearchService
from app.services.ai_matching import AiMatchingService, AiRateLimiter, create_query_log, finalize_query_log
from app.services.config_service import ConfigService
from app.services.i18n import resolve_language

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Parts search"])


def _client_ip(request: Request, db: Session) -> str:
    peer = request.client.host if request.client else "unknown"
    trusted = ConfigService(db).get("ai.trusted_proxy_ips", [])
    try:
        peer_address = ipaddress.ip_address(peer)
        trusted_peer = any(
            peer_address in ipaddress.ip_network(str(value), strict=False)
            for value in trusted if isinstance(value, str)
        )
    except ValueError:
        trusted_peer = False
    if trusted_peer:
        forwarded = request.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return peer


def _dump(result: SearchResult) -> dict:
    return result.model_dump(mode="json")


async def _part_number_with_cache(
    service: PartSearchService, cache: CacheService, query: str,
) -> SearchResult:
    key = f"{cache.part_number_key(query)}:lang:{service.lang}"
    try:
        cached = await cache.get(key)
        if cached is not None:
            parsed = SearchResult.model_validate(cached)
            part_ids = [candidate.part.id for candidate in parsed.candidates]
            active_ids = set(service.db.scalars(select(Part.id).where(
                Part.id.in_(part_ids), Part.is_active.is_(True)
            ))) if part_ids else set()
            if active_ids == set(part_ids):
                return parsed
    except Exception as error:  # Redis must never make catalogue search unavailable.
        logger.warning("part number cache read failed: %s", error)
    result = service.part_number(query)
    if result.candidates:
        try:
            await cache.set(key, result.model_dump(mode="json"), ttl=3600)
        except Exception as error:
            logger.warning("part number cache write failed: %s", error)
    return result


@router.get("/search")
async def search(
    request: Request,
    db: Annotated[Session, Depends(get_db)], cache: Annotated[CacheService, Depends(get_cache)],
    type: Literal["part_no", "oem", "machine", "engine", "text"] = Query(...),
    q: str = Query(..., min_length=1, max_length=500),
    model: str | None = Query(default=None, max_length=150),
    lang: Literal["zh", "en", "vi"] | None = None,
) -> dict:
    started = time.perf_counter()
    selected_lang = resolve_language(request, db, lang)
    session_id = request.headers.get("X-Session-Id") or request.headers.get("X-Request-Id") or "anonymous"
    log = create_query_log(db, session_id=session_id, client_ip=_client_ip(request, db), query_type=type,
                           query_text=q, request_data={"type": type, "q": q, "model": model, "lang": selected_lang})
    service = PartSearchService(db, selected_lang)
    if type == "part_no":
        result = await _part_number_with_cache(service, cache, q)
    elif type == "oem":
        result = service.oem(q)
    elif type == "machine":
        result = service.machine(q, model)
    elif type == "engine":
        result = service.engine(q)
    else:
        result = service.text(q, selected_lang)
    finalize_query_log(db, log, result, round((time.perf_counter() - started) * 1000))
    return success(_dump(result))


@router.post("/search")
async def comprehensive_search(
    request: Request, payload: SearchRequest, db: Annotated[Session, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache)],
) -> dict:
    del cache  # AI orchestration merges fresh DB evidence; exact GET caching remains independent.
    started = time.perf_counter()
    selected_lang = resolve_language(request, db, payload.lang)
    session_id = request.headers.get("X-Session-Id") or request.headers.get("X-Request-Id") or "anonymous"
    client_ip = _client_ip(request, db)
    if not AiRateLimiter(db).consume(client_ip):
        db.rollback()
        raise AppError("AI search rate limit exceeded", code=42901, status_code=429)
    log = create_query_log(db, session_id=session_id, client_ip=client_ip, query_type="ai",
                           query_text=payload.query, request_data=payload.model_dump(mode="json") | {"lang": selected_lang})
    result = await AiMatchingService(db).search(payload.query, selected_lang, payload.context, session_id, log.id)
    finalize_query_log(db, log, result, round((time.perf_counter() - started) * 1000), include_query_id=True)
    return success(_dump(result))


@router.get("/categories")
def categories(db: Annotated[Session, Depends(get_db)]) -> dict:
    return success(PartSearchService(db).category_navigation())


@router.get("/machines/hot")
def hot_machines(
    db: Annotated[Session, Depends(get_db)], limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    return success(PartSearchService(db).hot_machines(limit))


@router.get("/parts/hot")
def hot_parts(
    request: Request, db: Annotated[Session, Depends(get_db)], limit: int = Query(default=10, ge=1, le=50),
    lang: Literal["zh", "en", "vi"] | None = None,
) -> dict:
    return success(PartSearchService(db, resolve_language(request, db, lang)).hot_parts(limit))


@router.get("/parts/{part_id}")
def part_detail(part_id: str, request: Request, db: Annotated[Session, Depends(get_db)],
                lang: Literal["zh", "en", "vi"] | None = None) -> dict:
    detail = PartSearchService(db, resolve_language(request, db, lang)).part_detail(part_id)
    if detail is None:
        raise AppError("part not found", code=40401, status_code=404)
    return success(detail)
