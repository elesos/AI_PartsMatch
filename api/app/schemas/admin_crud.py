from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PageResult(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


class PartFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    sku: str = Field(min_length=1, max_length=100)
    part_no: str = Field(min_length=1, max_length=150)
    oem_no: str | None = Field(default=None, max_length=150)
    alternate_no: str | None = Field(default=None, max_length=150)
    brand: str = Field(min_length=1, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    name_zh: str = Field(min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    name_vi: str | None = Field(default=None, max_length=255)
    specs: dict[str, Any] = Field(default_factory=dict)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    stock: int = Field(default=0, ge=0)
    stock_status: Literal["in_stock", "low_stock", "out_of_stock", "discontinued"] = "in_stock"
    unit: str = Field(default="件", min_length=1, max_length=30)
    notes: str | None = None
    is_active: bool = True


class PartCreate(PartFields):
    pass


class PartUpdate(PartFields):
    pass


class PartImageResult(ORMModel):
    id: str
    file_id: str
    url: str
    sort_order: int
    image_type: Literal["product", "nameplate", "packaging"]


class PartImageUpdate(BaseModel):
    sort_order: int = Field(ge=0)
    image_type: Literal["product", "nameplate", "packaging"]


class PartBulkRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)
    action: Literal["activate", "deactivate"]

    @model_validator(mode="after")
    def unique_ids(self):
        self.ids = list(dict.fromkeys(self.ids))
        return self


class PartResult(PartFields, ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime
    images: list[PartImageResult] = Field(default_factory=list)


class MachineFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    machine_type: str = Field(min_length=1, max_length=100)
    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=150)
    series: str | None = Field(default=None, max_length=150)
    year: int | None = Field(default=None, ge=1900, le=2200)
    region: str | None = Field(default=None, max_length=100)
    engine_model: str | None = Field(default=None, max_length=150)
    notes: str | None = None


class MachineCreate(MachineFields):
    pass


class MachineUpdate(MachineFields):
    pass


class MachineResult(MachineFields, ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime


class MachinePartFields(BaseModel):
    machine_id: str = Field(min_length=1, max_length=36)
    part_id: str = Field(min_length=1, max_length=36)
    system: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    serial_from: str | None = Field(default=None, max_length=100)
    serial_to: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    priority: int = Field(default=0, ge=0)
    is_active: bool = True


class MachinePartCreate(MachinePartFields):
    pass


class MachinePartUpdate(MachinePartFields):
    pass


class MachinePartResult(MachinePartFields, ORMModel):
    id: str
    part_no: str | None = None
    part_name: str | None = None
    part_brand: str | None = None
    part_category: str | None = None
    created_at: datetime
    updated_at: datetime


class CsvImportResult(BaseModel):
    created: int
    valid: int
    processed: int
    dry_run: bool
    errors: list[dict[str, Any]]


class MachineTypeFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    code: str = Field(pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$", min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True


class MachineTypeCreate(MachineTypeFields):
    pass


class MachineTypeUpdate(MachineTypeFields):
    pass


class MachineTypeResult(MachineTypeFields, ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime


class CrossRefFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    source_part_id: str = Field(min_length=1, max_length=36)
    target_part_id: str = Field(min_length=1, max_length=36)
    relation_type: Literal[
        "OEM", "aftermarket", "replacement", "compatible", "equivalent", "supersedes"
    ] = "replacement"
    reliability: Decimal = Field(default=Decimal("1"), ge=0, le=1, max_digits=5, decimal_places=4)
    restrictions: str | None = Field(default=None, max_length=2000)
    brand: str | None = Field(default=None, max_length=100)
    priority: int = Field(default=0, ge=0, le=10000)
    source: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    status: Literal["pending", "active", "inactive", "rejected"] = "active"

    @model_validator(mode="after")
    def distinct_parts(self) -> "CrossRefFields":
        if self.source_part_id == self.target_part_id:
            raise ValueError("source_part_id and target_part_id must differ")
        return self


class CrossRefCreate(CrossRefFields):
    pass


class CrossRefUpdate(CrossRefFields):
    pass


class CrossRefResult(CrossRefFields, ORMModel):
    id: str
    source_part_no: str | None = None
    target_part_no: str | None = None
    source_part: dict[str, Any] | None = None
    target_part: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class AliasFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    part_id: str = Field(min_length=1, max_length=36)
    alias: str = Field(min_length=1, max_length=255)
    language: str = Field(default="zh", min_length=2, max_length=10)
    region: str | None = Field(default=None, max_length=20)
    source: str | None = Field(default=None, max_length=100)
    status: Literal["pending", "active", "rejected"] = "pending"


class AliasCreate(AliasFields):
    pass


class AliasUpdate(AliasFields):
    pass


class AliasStatusUpdate(BaseModel):
    status: Literal["active", "rejected"]


class AliasResult(AliasFields, ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime


class CategoryFields(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    parent_id: str | None = Field(default=None, max_length=36)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True


class CategoryCreate(CategoryFields):
    pass


class CategoryUpdate(CategoryFields):
    pass


class CategoryResult(CategoryFields, ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime
