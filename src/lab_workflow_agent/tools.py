"""Four read-only capabilities; model strings never select URLs or methods."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import AppError
from .source_client import LabStorageClient
from .source_models import MaterialRead, MaterialSearchArgs, Page, PageArgs


class MaterialIdArgs(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    material_id: int = Field(gt=0)


class LocationIdArgs(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    location_id: int = Field(gt=0)


@dataclass(frozen=True)
class ToolSpec:
    arguments: type[BaseModel]
    description: str


TOOL_REGISTRY = MappingProxyType({
    "search_materials": ToolSpec(MaterialSearchArgs,
        "Read one page of materials using filters. Defaults exclude archived records. "
        "low_stock=true includes zero stock; availability_status=low_stock requires positive "
        "unreserved stock. Include archived only when the user explicitly requests it."),
    "get_material": ToolSpec(MaterialIdArgs, "Read one material by its positive ID."),
    "list_locations": ToolSpec(PageArgs, "Read one page of locations; at most ten records."),
    "get_location": ToolSpec(LocationIdArgs, "Read one location by its positive ID."),
})


def tool_definitions() -> list[dict]:
    # One source of argument constraints: the same Pydantic models used locally.
    # Provider strict mode is disabled until its schema subset is verified end-to-end.
    return [{"type": "function", "function": {
        "name": name, "description": spec.description,
        "parameters": spec.arguments.model_json_schema(), "strict": False,
    }} for name, spec in TOOL_REGISTRY.items()]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Non-finite JSON constant")


def validate_call(name: str, arguments: str) -> BaseModel:
    if not isinstance(name, str) or name not in TOOL_REGISTRY:
        raise AppError("Unknown read-only tool.")
    if not isinstance(arguments, str) or len(arguments) > 8192:
        raise AppError("Tool arguments must be a bounded JSON string.")
    try:
        decoded = json.loads(arguments, object_pairs_hook=_unique_object,
                             parse_constant=_invalid_constant)
        return TOOL_REGISTRY[name].arguments.model_validate(decoded)
    except (ValueError, TypeError, RecursionError, ValidationError):
        raise AppError("Invalid read-only tool arguments.") from None


def _record(value: BaseModel) -> dict:
    result = value.model_dump(mode="json")
    if isinstance(value, MaterialRead):
        result["quantity_unreserved"] = value.quantity_unreserved
    return result


def dispatch(client: LabStorageClient, name: str, arguments: str, *,
             allow_archived: bool = False) -> dict:
    """allow_archived is trusted application policy, never a model argument."""
    args = validate_call(name, arguments)
    if name == "search_materials":
        if args.include_archived and not allow_archived:
            raise AppError("Archived search requires an explicit user request.")
        value = client.search_materials(**args.model_dump())
    elif name == "get_material":
        value = client.get_material(args.material_id)
    elif name == "list_locations":
        value = client.list_locations(**args.model_dump())
    elif name == "get_location":
        value = client.get_location(args.location_id)
    else:
        raise AppError("Unknown read-only tool.")

    records = value.items if isinstance(value, Page) else [value]
    if not allow_archived and any(isinstance(item, MaterialRead) and item.is_archived for item in records):
        raise AppError("Archived material requires an explicit user request.")
    if isinstance(value, Page):
        data = {key: getattr(value, key) for key in ("page", "size", "total", "pages")}
        data["items"] = [_record(item) for item in value.items]
        data["has_more"] = value.page < value.pages
    else:
        data = _record(value)
    return {"tool": name, "read_at": datetime.now(timezone.utc).isoformat(), "data": data}
