from typing import Any

from pydantic import BaseModel, Field


class ConfigUpsert(BaseModel):
    value: Any
    description: str | None = Field(default=None, max_length=500)
    is_secret: bool = False


class ConfigResult(BaseModel):
    key: str
    value: Any
    description: str | None
    is_secret: bool
