from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models import AiMatchEvidence, AiRateLimitEvent, LlmCallLog, Machine, Part, PartAlias, PartQueryLog
from app.schemas.ai_matching import EvidenceItem, SearchIntent
from app.schemas.search import SearchCandidate, SearchResult
from app.services.catalog_validation import normalize_part_number
from app.services.config_service import ConfigService
from app.services.part_search import PartSearchService

logger = logging.getLogger(__name__)

SAFETY_CATEGORIES = {"engine", "hydraulic", "electrical", "brake", "发动机", "液压", "电气", "制动"}
LANG_MARKERS = {
    "vi": re.compile(r"[ăâđêôơưĂÂĐÊÔƠƯ]|\b(?:máy|lọc|phanh|động cơ|phụ tùng)\b", re.I),
    "zh": re.compile(r"[\u3400-\u9fff]"),
}
CATEGORY_TERMS = {
    "filter": ("滤芯", "滤清器", "filter", "lọc"),
    "engine": ("发动机", "engine", "động cơ"),
    "hydraulic": ("液压", "hydraulic", "thủy lực"),
    "electrical": ("电气", "electrical", "điện"),
    "brake": ("制动", "刹车", "brake", "phanh"),
}


class LlmProvider(Protocol):
    async def structured(self, *, purpose: str, system: str, user: str, schema: dict[str, Any],
                         safety_identifier: str) -> tuple[dict[str, Any], dict[str, int | None]]: ...


class OpenAICompatibleProvider:
    def __init__(self, *, base_url: str, api_key: str, model: str, api_mode: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.api_mode = api_mode
        self.timeout = timeout

    async def structured(self, *, purpose: str, system: str, user: str, schema: dict[str, Any],
                         safety_identifier: str) -> tuple[dict[str, Any], dict[str, int | None]]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if self.api_mode == "responses":
            payload = {
                "model": self.model,
                "instructions": system,
                "input": user,
                "safety_identifier": safety_identifier,
                "text": {"format": {"type": "json_schema", "name": purpose, "strict": True, "schema": schema}},
            }
            url = f"{self.base_url}/responses"
        else:
            payload = {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_schema", "json_schema": {"name": purpose, "strict": True, "schema": schema}},
                "user": safety_identifier,
            }
            url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()
        if self.api_mode == "responses":
            content = body.get("output_text")
            if not content:
                for output in body.get("output", []):
                    for item in output.get("content", []):
                        if item.get("type") in {"output_text", "text"}:
                            content = item.get("text")
                            break
        else:
            message = body["choices"][0]["message"]
            if isinstance(message.get("parsed"), dict):
                parsed = message["parsed"]
                usage = body.get("usage", {})
                return parsed, {"input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens")}
            content = message.get("content")
        if not isinstance(content, str):
            raise ValueError("provider returned no structured output")
        parsed = _load_json_object(content)
        usage = body.get("usage", {})
        return parsed, {
            "input_tokens": usage.get("input_tokens", usage.get("prompt_tokens")),
            "output_tokens": usage.get("output_tokens", usage.get("completion_tokens")),
        }


def _load_json_object(value: str) -> dict[str, Any]:
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("structured output is not JSON")
        result = json.loads(text[start:end + 1])
    if not isinstance(result, dict):
        raise ValueError("structured output must be an object")
    return result


def detect_language(query: str, requested: str | None = None) -> str:
    if LANG_MARKERS["vi"].search(query):
        return "vi"
    if LANG_MARKERS["zh"].search(query):
        return "zh"
    return requested if requested in {"zh", "en", "vi"} else "en"


def rules_intent(query: str, requested_lang: str = "zh", context: dict[str, str] | None = None) -> SearchIntent:
    context = context or {}
    lang = detect_language(query, requested_lang)
    lowered = query.casefold()
    category = next((canonical for canonical, terms in CATEGORY_TERMS.items() if any(term in lowered for term in terms)), None)
    quantity_match = re.search(r"(?:x|×|数量|qty|quantity|số lượng)\s*[:：]?\s*(\d{1,4})|\b(\d{1,4})\s*(?:个|件|pcs?|cái)\b", query, re.I)
    quantity = int(next((item for item in quantity_match.groups() if item), "1")) if quantity_match else 1
    compact = re.sub(r"\s+", "", query)
    code_match = re.fullmatch(r"(?=.*\d)[A-Z0-9][A-Z0-9._/\-]{2,149}", compact, re.I)
    part_no = context.get("part_no") or (normalize_part_number(compact) if code_match else None)
    return SearchIntent(
        part_category=context.get("part_category") or category,
        machine_brand=context.get("machine_brand") or None,
        machine_model=context.get("machine_model") or None,
        serial_no=context.get("serial_no") or None,
        engine_model=context.get("engine_model") or None,
        part_no=part_no,
        quantity=quantity,
        lang=lang,
    )


def _error_type(error: Exception) -> str:
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        return "auth" if status in {401, 403} else "rate_limit" if status == 429 else "provider_http"
    if isinstance(error, (ValueError, KeyError, json.JSONDecodeError)):
        return "invalid_response"
    return "transport"


@dataclass
class AiRuntime:
    provider: LlmProvider | None
    provider_name: str
    api_mode: str
    model: str | None
    top_n: int
    exact_threshold: float
    high_threshold: float
    low_threshold: float
    close_gap: float
    safety_salt: str


class AiMatchingService:
    def __init__(self, db: Session, provider: LlmProvider | None = None) -> None:
        self.db = db
        config = ConfigService(db)
        api_key = str(config.get("ai.api_key", "") or "")
        model = str(config.get("ai.model", "") or "")
        api_mode = str(config.get("ai.api_mode", "responses"))
        configured = provider
        if configured is None and api_key and model:
            configured = OpenAICompatibleProvider(
                base_url=str(config.get("ai.base_url", "https://api.openai.com/v1")), api_key=api_key,
                model=model, api_mode=api_mode, timeout=float(config.get("ai.timeout_seconds", 20)),
            )
        self.runtime = AiRuntime(
            provider=configured, provider_name="mock" if provider is not None else ("openai_compatible" if configured else "rules"),
            api_mode=api_mode, model=model or None, top_n=max(1, min(int(config.get("ai.top_n", 10)), 50)),
            exact_threshold=float(config.get("ai.exact_threshold", 0.9)),
            high_threshold=float(config.get("ai.high_threshold", 0.7)),
            low_threshold=float(config.get("ai.low_threshold", 0.4)),
            close_gap=float(config.get("ai.close_candidate_gap", 0.05)),
            safety_salt=str(config.get("ai.safety_salt", "partsmatch-safety-v1")),
        )

    def safety_identifier(self, session_id: str) -> str:
        return hashlib.sha256(f"{self.runtime.safety_salt}:{session_id}".encode()).hexdigest()

    async def _call(self, *, purpose: str, system: str, user: str, schema: dict[str, Any],
                    session_id: str, query_log_id: str | None = None) -> dict[str, Any] | None:
        provider = self.runtime.provider
        if provider is None:
            return None
        started = time.perf_counter()
        prompt_hash = hashlib.sha256(f"{system}\n{user}".encode()).hexdigest()
        status, error_type, error_message, usage, result = "success", None, None, {}, None
        try:
            result, usage = await provider.structured(
                purpose=purpose, system=system, user=user, schema=schema,
                safety_identifier=self.safety_identifier(session_id),
            )
        except Exception as error:
            status, error_type, error_message = "failed", _error_type(error), str(error)[:500]
            logger.warning("LLM %s failed (%s): %s", purpose, error_type, error)
        self.db.add(LlmCallLog(
            query_log_id=query_log_id, provider=self.runtime.provider_name, api_mode=self.runtime.api_mode,
            model=self.runtime.model, prompt_hash=prompt_hash, safety_identifier=self.safety_identifier(session_id),
            input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
            duration_ms=round((time.perf_counter() - started) * 1000), status=status,
            error_type=error_type, error_message=error_message,
        ))
        self.db.flush()
        return result

    async def parse_intent(self, query: str, lang: str, context: dict[str, str], session_id: str,
                           query_log_id: str | None = None) -> tuple[SearchIntent, str]:
        fallback = rules_intent(query, lang, context)
        nullable_string = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        # OpenAI strict structured outputs requires every property to be required;
        # optional business values are represented as nullable instead of omitted.
        schema = {
            "type": "object", "additionalProperties": False,
            "properties": {
                "intent": {"type": "string", "enum": ["find_part"]},
                "part_category": nullable_string, "machine_brand": nullable_string,
                "machine_model": nullable_string, "serial_no": nullable_string,
                "engine_model": nullable_string, "part_no": nullable_string,
                "quantity": {"type": "integer", "minimum": 1, "maximum": 9999},
                "lang": {"type": "string", "enum": ["zh", "en", "vi"]},
            },
            "required": ["intent", "part_category", "machine_brand", "machine_model", "serial_no",
                         "engine_model", "part_no", "quantity", "lang"],
        }
        result = await self._call(
            purpose="part_search_intent",
            system=("Extract a parts-search intent. Normalize synonymous categories to filter, engine, hydraulic, "
                    "electrical, brake where possible. Preserve identifiers. Detect zh/en/vi. Return only schema data."),
            user=json.dumps({"query": query, "lang_hint": lang, "context": context}, ensure_ascii=False),
            schema=schema, session_id=session_id, query_log_id=query_log_id,
        )
        if result is None:
            return fallback, "rules"
        try:
            parsed = SearchIntent.model_validate(result)
            # Explicit caller context is trusted above model extraction.
            merged = parsed.model_copy(update={key: value for key, value in context.items() if key in SearchIntent.model_fields and value})
            return merged, "llm"
        except Exception as error:
            logger.warning("invalid intent schema, using rules: %s", error)
            return fallback, "rules"

    def _semantic_category(self, intent: SearchIntent) -> SearchResult:
        term = intent.part_category
        if not term:
            return SearchResult(query_type="natural", extracted_info=intent.model_dump(), match_status="not_found")
        pattern = f"%{term.replace('%', '').replace('_', '')}%"
        alias_ids = select(PartAlias.part_id).where(PartAlias.status == "active", PartAlias.alias.ilike(pattern))
        parts = list(self.db.scalars(select(Part).where(
            Part.is_active.is_(True), or_(Part.category.ilike(pattern), Part.name_zh.ilike(pattern),
                                          Part.name_en.ilike(pattern), Part.name_vi.ilike(pattern), Part.id.in_(alias_ids)),
        ).order_by(Part.part_no).limit(50)))
        candidates = PartSearchService(self.db, intent.lang)._candidates(
            parts, 0.65, "结构化类别/名称语义匹配",
            evidence=[{"type": "ai", "content": f"标准类别或名称匹配: {term}", "source_ref": "part_catalog", "confidence": 0.65}],
        )
        return SearchResult(query_type="natural", extracted_info=intent.model_dump(),
                            match_status="low" if parts else "not_found", candidates=candidates)

    @staticmethod
    def _normalize_evidence(candidate: SearchCandidate, route: str) -> list[dict[str, Any]]:
        mapping = {"part_no": "part_no", "oem": "oem", "machine": "machine", "engine": "engine", "natural": "ai"}
        normalized = []
        for item in candidate.evidence:
            if isinstance(item, str):
                raw = {"content": item}
            else:
                raw = item
            evidence_type = raw.get("type") or mapping.get(route, "ai")
            if evidence_type not in EvidenceItem.model_fields["type"].annotation.__args__:
                evidence_type = mapping.get(route, "ai")
            content = raw.get("content") or (
                f"{raw.get('field')}={raw.get('value')}" if raw.get("field") else candidate.reason
            )
            normalized.append(EvidenceItem(
                type=evidence_type, content=str(content), source_ref=str(raw.get("source_ref") or "part_catalog"),
                confidence=float(raw.get("confidence", candidate.confidence)),
            ).model_dump())
        if not normalized:
            normalized.append(EvidenceItem(type=mapping.get(route, "ai"), content=candidate.reason,
                                           source_ref="part_catalog", confidence=candidate.confidence).model_dump())
        return normalized

    async def search(self, query: str, lang: str, context: dict[str, str], session_id: str,
                     query_log_id: str | None = None) -> SearchResult:
        intent, intent_provider = await self.parse_intent(query, lang, context, session_id, query_log_id)
        search = PartSearchService(self.db, lang)
        routes: list[SearchResult] = []
        if intent.part_no:
            routes.extend([search.part_number(intent.part_no), search.oem(intent.part_no)])
        if intent.machine_brand:
            routes.append(search.machine(intent.machine_brand, intent.machine_model))
        if intent.engine_model:
            routes.append(search.engine(intent.engine_model))
        if not intent.machine_brand:
            machine = self.db.scalar(select(Machine).where(func.upper(Machine.model) == query.upper()).order_by(Machine.brand).limit(1))
            if machine:
                intent = intent.model_copy(update={"machine_brand": machine.brand, "machine_model": machine.model, "part_no": None})
                routes.append(search.machine(machine.brand, machine.model))
        if not intent.engine_model:
            engine_model = self.db.scalar(select(Machine.engine_model).where(
                func.upper(Machine.engine_model) == query.upper()
            ).limit(1))
            if engine_model:
                intent = intent.model_copy(update={"engine_model": engine_model, "part_no": None})
                routes.append(search.engine(engine_model))
        # Always retain reviewed multilingual catalogue evidence.
        routes.append(search.text(query, intent.lang))
        if intent.part_category:
            routes.append(self._semantic_category(intent))

        merged: dict[str, SearchCandidate] = {}
        priority = {"part_no": 0.08, "oem": 0.06, "machine": 0.04, "engine": 0.02, "natural": 0.0}
        for result in routes:
            for candidate in result.candidates:
                candidate.evidence = self._normalize_evidence(candidate, result.query_type)
                adjusted = min(1.0, candidate.confidence + priority[result.query_type])
                previous = merged.get(candidate.part.id)
                if previous is None:
                    candidate.confidence = adjusted
                    merged[candidate.part.id] = candidate
                else:
                    previous.confidence = max(previous.confidence, adjusted)
                    previous.evidence = list({json.dumps(item, sort_keys=True, ensure_ascii=False): item
                                              for item in previous.evidence + candidate.evidence}.values())
                    previous.reason = "；".join(dict.fromkeys([previous.reason, candidate.reason]))
        candidates = sorted(merged.values(), key=lambda item: (-item.confidence, item.part.part_no))

        if candidates and self.runtime.provider:
            allowed = [{"part_id": item.part.id, "confidence": item.confidence,
                        "reason": item.reason, "evidence": item.evidence} for item in candidates]
            rerank_schema = {
                "type": "object", "additionalProperties": False,
                "properties": {"ranked": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                    "properties": {"part_id": {"type": "string"}, "score": {"type": "number", "minimum": 0, "maximum": 1},
                                   "reason": {"type": "string"}}, "required": ["part_id", "score", "reason"]}}},
                "required": ["ranked"],
            }
            reranked = await self._call(
                purpose="part_candidate_rerank",
                system="Rerank only supplied candidates. Never create a part_id. Scores must reflect supplied evidence.",
                user=json.dumps({"intent": intent.model_dump(), "candidates": allowed}, ensure_ascii=False),
                schema=rerank_schema, session_id=session_id, query_log_id=query_log_id,
            )
            if isinstance(reranked, dict) and isinstance(reranked.get("ranked"), list):
                by_id = {item.part.id: item for item in candidates}
                safe_ranked, seen = [], set()
                for row in reranked["ranked"]:
                    part_id = row.get("part_id") if isinstance(row, dict) else None
                    if part_id in by_id and part_id not in seen:
                        item = by_id[part_id]
                        item.confidence = min(item.confidence, max(0.0, min(float(row.get("score", item.confidence)), 1.0)))
                        item.reason = str(row.get("reason") or item.reason)[:1000]
                        item.evidence.append(EvidenceItem(type="ai", content="LLM 仅对数据库候选进行了重排",
                                                         source_ref="llm_rerank", confidence=item.confidence).model_dump())
                        safe_ranked.append(item)
                        seen.add(part_id)
                candidates = safe_ranked + [item for item in candidates if item.part.id not in seen]

        candidates = candidates[:self.runtime.top_n]
        for candidate in candidates:
            category = (candidate.part.category or "").casefold()
            if category in SAFETY_CATEGORIES:
                candidate.confidence = min(candidate.confidence, 0.89)
            candidate.match_status = self.status(candidate.confidence)
        confidence = candidates[0].confidence if candidates else 0.0
        status = self.status(confidence)
        if not candidates and len(query.strip()) < 2:
            status = "insufficient"
        close = len(candidates) > 1 and abs(candidates[0].confidence - candidates[1].confidence) < self.runtime.close_gap
        safety_low = bool(candidates and (candidates[0].part.category or "").casefold() in SAFETY_CATEGORIES and confidence < 0.9)
        need_manual = confidence < self.runtime.low_threshold or close or safety_low
        questions = self.follow_up_questions(intent, confidence, close, safety_low)
        evidence_types = {entry.get("type") for entry in candidates[0].evidence if isinstance(entry, dict)} if candidates else set()
        query_type = ("part_no" if "part_no" in evidence_types else "oem" if "oem" in evidence_types else
                      "machine" if "machine" in evidence_types else "engine" if "engine" in evidence_types else
                      "part_no" if intent.part_no else "natural")
        if not candidates:
            questions.append("M6 AI 匹配未找到结果，请补充信息或转人工。")
        return SearchResult(
            query_type=query_type, extracted_info=intent.model_dump(), match_status=status,
            candidates=candidates, need_manual=need_manual, follow_up_questions=questions,
            suggestions=questions, provider=intent_provider,
        )

    def status(self, confidence: float) -> str:
        if confidence >= self.runtime.exact_threshold:
            return "exact"
        if confidence >= self.runtime.high_threshold:
            return "high"
        if confidence >= self.runtime.low_threshold:
            return "low"
        return "not_found"

    @staticmethod
    def follow_up_questions(intent: SearchIntent, confidence: float, close: bool, safety_low: bool) -> list[str]:
        questions = []
        if not intent.part_no:
            questions.append("请提供配件编号或 OEM 编号（如有）。")
        if not intent.machine_model:
            questions.append("请提供设备品牌、型号和序列号。")
        if close:
            questions.append("多个候选很接近，请确认尺寸、接口或铭牌信息。")
        if safety_low:
            questions.append("该配件属于安全关键类别，请上传铭牌/旧件照片并由人工确认。")
        if confidence < 0.4:
            questions.append("是否转交人工配件专家处理？")
        return list(dict.fromkeys(questions))


class AiRateLimiter:
    """DB sliding window fallback; row lock serializes checks for the same client on PostgreSQL."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.limit = max(1, min(int(ConfigService(db).get("ai.rate_limit_per_minute", 20)), 1000))

    def consume(self, client_ip: str) -> bool:
        client_key = hashlib.sha256(client_ip.encode()).hexdigest()
        cutoff = datetime.now(UTC) - timedelta(minutes=1)
        # A transaction-scoped advisory lock makes count+insert atomic per IP on PostgreSQL.
        if self.db.bind is not None and self.db.bind.dialect.name == "postgresql":
            lock_key = int(client_key[:15], 16)
            self.db.execute(select(func.pg_advisory_xact_lock(lock_key)))
        self.db.execute(delete(AiRateLimitEvent).where(AiRateLimitEvent.created_at < cutoff - timedelta(minutes=5)))
        count = self.db.scalar(select(func.count()).select_from(AiRateLimitEvent).where(
            AiRateLimitEvent.client_key == client_key, AiRateLimitEvent.created_at >= cutoff,
        )) or 0
        if count >= self.limit:
            return False
        self.db.add(AiRateLimitEvent(client_key=client_key))
        self.db.flush()
        return True


def create_query_log(db: Session, *, session_id: str, client_ip: str, query_type: str,
                     query_text: str, request_data: dict[str, Any], raw_input: dict[str, Any] | None = None) -> PartQueryLog:
    item = PartQueryLog(session_id=session_id, user_id=None, client_ip=client_ip, query_type=query_type,
                        query_text=query_text, request_data=request_data, raw_input=raw_input or request_data)
    db.add(item)
    db.flush()
    return item


def finalize_query_log(db: Session, item: PartQueryLog, result: SearchResult, duration_ms: int,
                       *, include_query_id: bool = False) -> None:
    dumped = result.model_dump(mode="json")
    item.extracted_info = result.extracted_info
    item.ai_result = dumped
    item.result_count = len(result.candidates)
    item.confidence = result.candidates[0].confidence if result.candidates else 0
    item.match_status = result.match_status
    item.need_manual = result.need_manual
    item.duration_ms = duration_ms
    for candidate in result.candidates:
        db.add(AiMatchEvidence(query_log_id=item.id, part_id=candidate.part.id,
                               confidence=candidate.confidence, reason=candidate.reason,
                               evidence=[entry for entry in candidate.evidence if isinstance(entry, dict)]))
    if include_query_id:
        result.query_id = item.id
    db.commit()
