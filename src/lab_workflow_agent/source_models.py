from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MaterialRead(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    id: int = Field(gt=0)
    material_code: str
    material_name: str
    material_type: str

    quantity_available: int = Field(ge=0)
    quantity_reserved: int = Field(ge=0)
    unit: str
    minimum_quantity: int = Field(ge=0)

    availability_status: str
    qc_status: str

    location_id: int | None = Field(default=None, gt=0)
    is_archived: bool
    updated_at: str | None = None

    @property
    def quantity_unreserved(self) -> int:
        return self.quantity_available - self.quantity_reserved


class SourceRead(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore", hide_input_in_errors=True)


class UserRead(SourceRead):
    id: int = Field(gt=0)
    username: str
    email: str
    role: str


class LocationRead(SourceRead):
    id: int = Field(gt=0)
    name: str
    location_type: str
    parent_location_id: int | None = Field(default=None, gt=0)
    temperature_zone: str | None = None
    description: str | None = None


ItemT = TypeVar("ItemT")


class Page(SourceRead, Generic[ItemT]):
    items: list[ItemT]
    page: int = Field(ge=1)
    size: int = Field(ge=1, le=10)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)

    @model_validator(mode="after")
    def consistent_page(self):
        if self.pages != (self.total + self.size - 1) // self.size:
            raise ValueError("Inconsistent page count")
        if len(self.items) > min(self.size, max(0, self.total - (self.page - 1) * self.size)):
            raise ValueError("Too many page items")
        return self


class ErrorDetail(SourceRead):
    code: str
    message: str


class ErrorResponse(SourceRead):
    error: ErrorDetail


class PageArgs(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=10, ge=1, le=10)


class MaterialSearchArgs(PageArgs):
    keyword: str | None = Field(default=None, min_length=1, max_length=255)
    material_type: str | None = Field(default=None, min_length=1, max_length=80)
    source: str | None = Field(default=None, min_length=1, max_length=255)
    qc_status: Literal["pending", "passed", "failed"] | None = None
    availability_status: Literal["available", "low_stock", "unavailable"] | None = None
    location_id: int | None = Field(default=None, gt=0)
    low_stock: bool = False
    include_archived: bool = False
