from typing import Any, Literal

from pydantic import BaseModel, Field


class ImageUploadItem(BaseModel):
    image_id: str
    url: str
    mime_type: str
    size: int


class ImageUploadResult(BaseModel):
    images: list[ImageUploadItem]


class OCRResult(BaseModel):
    image_id: str
    raw_text: str
    lines: list[str]


class ParsedImageResult(OCRResult):
    image_type: Literal[
        "part_photo", "machine_nameplate", "engine_nameplate", "package_label",
        "old_part_number", "exploded_diagram", "unknown",
    ]
    confidence: float = Field(ge=0, le=1)
    extracted_info: dict[str, Any]


class ImageMatchRequest(BaseModel):
    image_ids: list[str] = Field(min_length=1, max_length=5)
    user_hint: str | None = Field(default=None, max_length=500)
    lang: Literal["zh", "en", "vi"] = "en"
