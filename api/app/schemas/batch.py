from pydantic import BaseModel, ConfigDict, Field, model_validator


class BatchSelection(BaseModel):
    row_index: int = Field(ge=1)
    part_id: str = Field(min_length=1, max_length=36)
    quantity: int = Field(ge=1, le=100_000)
    confirmed: bool = False


class BatchCartRequest(BaseModel):
    selections: list[BatchSelection] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_rows(self):
        if len({item.row_index for item in self.selections}) != len(self.selections):
            raise ValueError("row_index must be unique")
        return self


class BatchTicketRequest(BaseModel):
    row_indexes: list[int] | None = Field(default=None, max_length=500)
    contact_name: str = Field(min_length=1, max_length=100)
    contact_info: str = Field(min_length=1, max_length=255)
    communication_tool: str = Field(pattern="^(whatsapp|wechat|zalo|telegram)$")
    country: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def valid_rows(self):
        if self.row_indexes is not None:
            if any(value < 1 for value in self.row_indexes):
                raise ValueError("row_indexes must be positive")
            if len(set(self.row_indexes)) != len(self.row_indexes):
                raise ValueError("row_indexes must be unique")
        return self


class BatchRowUpdate(BaseModel):
    """The deliberately small, user-editable subset of an imported row."""

    model_config = ConfigDict(extra="forbid")

    machine_brand: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=200)
    engine_model: str | None = Field(default=None, max_length=200)
    part_name: str | None = Field(default=None, max_length=500)
    part_no: str | None = Field(default=None, max_length=200)
    oem_no: str | None = Field(default=None, max_length=200)
    system: str | None = Field(default=None, max_length=200)
    quantity: int | None = Field(default=None, ge=1, le=100_000)

    @model_validator(mode="after")
    def not_empty(self):
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for field in self.model_fields_set:
            value = getattr(self, field)
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                raise ValueError(f"{field} must not contain formula-like content")
        return self
