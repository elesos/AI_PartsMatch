from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SearchIntent(BaseModel):
    intent: Literal["find_part"] = "find_part"
    part_category: str | None = Field(default=None, max_length=100)
    machine_brand: str | None = Field(default=None, max_length=100)
    machine_model: str | None = Field(default=None, max_length=150)
    serial_no: str | None = Field(default=None, max_length=150)
    engine_model: str | None = Field(default=None, max_length=150)
    part_no: str | None = Field(default=None, max_length=150)
    quantity: int = Field(default=1, ge=1, le=9999)
    lang: Literal["zh", "en", "vi"]

    @field_validator("part_category", "machine_brand", "machine_model", "serial_no", "engine_model", "part_no")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class EvidenceItem(BaseModel):
    type: Literal["part_no", "oem", "replacement", "machine", "engine", "ocr", "ai"]
    content: str = Field(min_length=1, max_length=1000)
    source_ref: str = Field(min_length=1, max_length=255)
    confidence: float = Field(ge=0, le=1)


class QueryLogListItem(BaseModel):
    id: str
    session_id: str | None
    user_id: str | None
    query_type: str
    source: Literal["text", "image", "excel", "manual"]
    source_id: str | None
    query_text: str | None
    result_count: int
    confidence: float | None
    match_status: str | None
    need_manual: bool
    duration_ms: int | None
    created_at: datetime


class QueryLogDetail(QueryLogListItem):
    client_ip: str | None
    request_data: dict[str, Any]
    raw_input: dict[str, Any] | None
    extracted_info: dict[str, Any] | None
    ai_result: dict[str, Any] | None
    evidence: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    uploaded_files: list[dict[str, Any]]
    llm_calls: list[dict[str, Any]]
    selected_parts: list[dict[str, Any]]
    correction: dict[str, Any] | None


class QueryLogPage(BaseModel):
    items: list[QueryLogListItem]
    page: int
    page_size: int
    total: int


class QueryLogCorrectionCreate(BaseModel):
    recommended_part_id: str | None = Field(default=None, max_length=36)
    correct_part_id: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("reason must contain at least 3 characters")
        return value
