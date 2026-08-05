from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SearchType = Literal["part_no", "oem", "machine", "engine", "text"]
QueryType = Literal["part_no", "oem", "machine", "engine", "natural"]
MatchStatus = Literal["exact", "high", "low", "multiple", "insufficient", "not_found"]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    lang: Literal["zh", "en", "vi"] | None = None
    context: dict[str, str] = Field(default_factory=dict)

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be blank")
        return value


class PartSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sku: str
    part_no: str
    oem_no: str | None
    brand: str
    category: str | None
    name: str
    name_zh: str
    name_en: str | None
    name_vi: str | None
    specs: dict[str, Any]
    price: float | None
    stock: int
    images: list[dict[str, Any]] = Field(default_factory=list)


class SearchCandidate(BaseModel):
    part: PartSummary
    confidence: float = Field(ge=0, le=1)
    reason: str
    evidence: list[dict[str, Any] | str] = Field(default_factory=list)
    relation_type: str | None = None
    reliability: float | None = Field(default=None, ge=0, le=1)
    fitments: list[dict[str, Any]] = Field(default_factory=list)
    requires_serial_confirmation: bool = False
    match_status: Literal["exact", "high", "low", "not_found"] | None = None


class SearchResult(BaseModel):
    query_type: QueryType
    extracted_info: dict[str, Any] = Field(default_factory=dict)
    match_status: MatchStatus
    candidates: list[SearchCandidate] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    groups: dict[str, list[str]] = Field(default_factory=dict)
    category_navigation: list[dict[str, Any]] = Field(default_factory=list)
    need_manual: bool = False
    follow_up_questions: list[str] = Field(default_factory=list)
    provider: Literal["llm", "rules"] = "rules"
    query_id: str | None = None
