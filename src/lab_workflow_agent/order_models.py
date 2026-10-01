"""Strict source order contracts; no model-selected write tools."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderCreate(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid', hide_input_in_errors=True)
    material_id: int = Field(gt=0)
    requested_quantity: int = Field(gt=0, le=1_000_000)
    request_notes: str | None = Field(default=None, max_length=5000)

    @field_validator('request_notes', mode='before')
    @classmethod
    def trim(cls, value):
        return (value.strip() or None) if isinstance(value, str) else value

    def canonical(self) -> str:
        import json
        return json.dumps(self.model_dump(), sort_keys=True, separators=(',', ':'), ensure_ascii=True)


class OrderRead(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra='ignore', hide_input_in_errors=True)
    id: int = Field(gt=0)
    requested_by_user_id: int = Field(gt=0)
    material_id: int = Field(gt=0)
    requested_quantity: int = Field(gt=0)
    reserved_quantity: int = Field(ge=0)
    status: Literal['submitted', 'approved', 'rejected', 'fulfilled', 'canceled']
    request_notes: str | None = Field(default=None, max_length=5000)
    is_archived: bool
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator('created_at', 'updated_at')
    @classmethod
    def timestamp(cls, value):
        if value is not None:
            datetime.fromisoformat(value)
        return value
