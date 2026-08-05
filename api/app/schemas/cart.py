from typing import Literal

from pydantic import BaseModel, Field, field_validator


MatchStatus = Literal["exact", "high", "multiple", "insufficient", "not_found"]
CartSource = Literal["direct", "search", "image", "batch", "manual"]


class CartAdd(BaseModel):
    part_id: str = Field(min_length=1, max_length=36)
    quantity: int = Field(default=1, ge=1, le=100_000)
    match_status: MatchStatus = "exact"
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: CartSource = "direct"
    need_confirm: bool = False


class CartUpdate(BaseModel):
    quantity: int = Field(ge=1, le=100_000)


class CartFromMatch(BaseModel):
    part_id: str = Field(min_length=1, max_length=36)
    quantity: int = Field(default=1, ge=1, le=100_000)
    query_id: str | None = Field(default=None, min_length=1, max_length=36)
    match_status: MatchStatus
    confidence: float = Field(ge=0, le=1)
    source: Literal["search", "image", "batch", "manual"] = "search"


class InquirySubmit(BaseModel):
    contact_name: str = Field(min_length=1, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    contact_method: str = Field(min_length=1, max_length=255)
    communication_tool: Literal["whatsapp", "wechat", "zalo", "telegram", "phone", "email", "other"]
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("contact_name", "contact_method")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("country")
    @classmethod
    def blank_country_as_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None
