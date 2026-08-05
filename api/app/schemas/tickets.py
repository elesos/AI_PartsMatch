from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TicketStatus = Literal["pending", "processing", "need_info", "matched", "in_cart", "closed"]


class TicketCreate(BaseModel):
    contact_name: str = Field(min_length=1, max_length=100)
    country: str = Field(default="", max_length=100)
    contact_info: str = Field(min_length=1, max_length=255)
    communication_tool: Literal["whatsapp", "wechat", "zalo", "telegram"]
    machine_type: str = Field(default="", max_length=100)
    machine_brand: str = Field(default="", max_length=100)
    machine_model: str = Field(default="", max_length=150)
    serial_no: str = Field(default="", max_length=150)
    engine_model: str = Field(default="", max_length=150)
    part_description: str = Field(min_length=1, max_length=5000)
    quantity: int = Field(default=1, ge=1, le=100_000)
    image_ids: list[str] = Field(default_factory=list, max_length=20)
    excel_batch_id: str | None = Field(default=None, max_length=36)
    note: str = Field(default="", max_length=5000)
    ai_preliminary_result: dict[str, Any] = Field(default_factory=dict)

    @field_validator("contact_name", "contact_info", "part_description")
    @classmethod
    def required_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("excel_batch_id", mode="before")
    @classmethod
    def blank_batch_is_none(cls, value):
        return None if value == "" else value


class TicketSupplement(BaseModel):
    content: str = Field(min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class TicketStatusUpdate(BaseModel):
    status: TicketStatus
    note: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def validate_note(self):
        self.note = self.note.strip()
        if self.status in {"need_info", "closed"} and not self.note:
            raise ValueError("note is required when requesting information or closing a ticket")
        return self


class TicketAssign(BaseModel):
    assignee_id: str = Field(min_length=1, max_length=36)


class TicketResolve(BaseModel):
    resolved_part_ids: list[str] = Field(min_length=1, max_length=100)
    match_evidence: str = Field(min_length=1, max_length=5000)
    internal_note: str = Field(default="", max_length=5000)
    quantities: dict[str, int] = Field(default_factory=dict)
    confidences: dict[str, float] = Field(default_factory=dict)
    reasons: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_parts(self):
        if len(set(self.resolved_part_ids)) != len(self.resolved_part_ids):
            raise ValueError("resolved_part_ids must be unique")
        unknown = (set(self.quantities) | set(self.confidences) | set(self.reasons)) - set(self.resolved_part_ids)
        if unknown:
            raise ValueError("quantities keys must be resolved_part_ids")
        if any(value < 1 or value > 100_000 for value in self.quantities.values()):
            raise ValueError("quantities must be between 1 and 100000")
        if any(value < 0 or value > 1 for value in self.confidences.values()):
            raise ValueError("confidences must be between 0 and 1")
        self.reasons = {key: value.strip() for key, value in self.reasons.items()}
        return self


class TicketAdminNote(BaseModel):
    content: str = Field(min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def note_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class TicketListQuery(BaseModel):
    status: TicketStatus | None = None
    assignee_id: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    machine_brand: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort: Literal["priority", "created_at", "updated_at"] = "priority"
    order: Literal["asc", "desc"] = "asc"
