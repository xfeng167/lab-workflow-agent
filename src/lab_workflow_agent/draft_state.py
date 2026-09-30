"""Pure in-memory draft transitions. No networking, persistence, or write payloads."""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .config import AppError
from .provider import Message
from .source_models import MaterialRead, UserRead

MAX_QUANTITY = 1_000_000
WARNING = "DRAFT ONLY — NO ORDER CREATED"


class FrozenModel(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)


class MaterialSnapshot(MaterialRead):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)


class Identity(FrozenModel):
    id: int = Field(gt=0)
    username: str
    role: str


class Quantity(FrozenModel):
    value: int = Field(gt=0, le=MAX_QUANTITY)


class Notes(FrozenModel):
    value: str | None = Field(default=None, max_length=5000)

    @field_validator("value", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class DraftState(FrozenModel):
    original_goal: str = Field(min_length=1, max_length=2000)
    search_goal: str = Field(min_length=1, max_length=2000)
    user: Identity
    messages: tuple[Message, ...] = ()
    candidates: tuple[MaterialSnapshot, ...] = Field(default=(), max_length=5)
    candidate_revision: int = Field(default=0, ge=0)
    search_filters: str = "none"
    search_performed: bool = False
    has_more: bool = False
    selected: MaterialSnapshot | None = None
    requested_quantity: int | None = Field(default=None, gt=0, le=MAX_QUANTITY)
    request_notes: str | None = Field(default=None, max_length=5000)
    read_at: str | None = None
    revision: int = Field(default=1, ge=1)
    abandoned: bool = False

    @property
    def unresolved(self) -> tuple[str, ...]:
        if self.abandoned:
            return ()
        missing = []
        if self.selected is None:
            missing.append("material selection")
        elif self.selected.is_archived:
            missing.append("non-archived material")
        if self.requested_quantity is None:
            missing.append("quantity")
        elif self.selected and self.requested_quantity > self.selected.quantity_unreserved:
            missing.append("sufficient advisory stock")
        return tuple(missing)

    @property
    def status(self) -> Literal["collecting", "ready", "abandoned"]:
        return "abandoned" if self.abandoned else "collecting" if self.unresolved else "ready"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start(goal: str, user: UserRead) -> DraftState:
    try:
        return DraftState(original_goal=goal.strip(), search_goal=goal.strip(),
                          user=Identity(id=user.id, username=user.username, role=user.role))
    except (ValidationError, AttributeError):
        raise AppError("A draft needs a goal of 1–2000 characters and a valid source user.") from None


def change(state: DraftState, **updates) -> DraftState:
    if state.abandoned:
        raise AppError("This draft is abandoned. Start a new session.")
    values = {name: getattr(state, name) for name in DraftState.model_fields}
    values.update(updates, revision=state.revision + 1)
    try:
        return DraftState.model_validate(values)
    except ValidationError:
        raise AppError("Invalid draft update; the prior draft was preserved.") from None


def record_candidates(state: DraftState, goal: str, materials: list[MaterialRead],
                      filters: str, has_more: bool) -> DraftState:
    if len(materials) > 5 or len({m.id for m in materials}) != len(materials):
        raise AppError("Source candidate set must contain at most five unique IDs.")
    snapshots = tuple(MaterialSnapshot.model_validate(m.model_dump()) for m in materials)
    return change(state, search_goal=goal, candidates=snapshots, selected=None, read_at=None,
                  search_filters=filters, has_more=has_more, search_performed=True,
                  candidate_revision=state.candidate_revision + 1)


def select(state: DraftState, material_id: int, candidate_revision: int,
           material: MaterialRead) -> DraftState:
    if (type(material_id) is not int or material_id <= 0
            or type(candidate_revision) is not int or candidate_revision != state.candidate_revision
            or material_id not in {m.id for m in state.candidates}):
        raise AppError("Select one displayed material ID from the current candidate revision.")
    if material.id != material_id:
        raise AppError("Source material does not match the selected ID.")
    return change(state, selected=MaterialSnapshot.model_validate(material.model_dump()), read_at=now())


def set_quantity(state: DraftState, value: int) -> DraftState:
    try:
        quantity = Quantity(value=value)
    except ValidationError:
        raise AppError(f"Quantity must be an integer from 1 to {MAX_QUANTITY}; no rounding or conversion.") from None
    return change(state, requested_quantity=quantity.value)


def set_notes(state: DraftState, value: str | None) -> DraftState:
    try:
        notes = Notes(value=value)
    except ValidationError:
        raise AppError("Notes must be text of at most 5000 characters, or cleared.") from None
    return change(state, request_notes=notes.value)


def refresh(state: DraftState, material: MaterialRead) -> DraftState:
    if state.selected is None or state.selected.id != material.id:
        raise AppError("Select a material before refreshing it.")
    return change(state, selected=MaterialSnapshot.model_validate(material.model_dump()), read_at=now())


def invalidate_material(state: DraftState) -> DraftState:
    return change(state, selected=None, candidates=(), read_at=None,
                  candidate_revision=state.candidate_revision + 1)


def reset(state: DraftState) -> DraftState:
    return change(state, search_goal=state.original_goal, candidates=(), selected=None,
                  requested_quantity=None, request_notes=None, read_at=None, messages=(),
                  candidate_revision=state.candidate_revision + 1, search_performed=False,
                  search_filters="none", has_more=False)


def abandon(state: DraftState) -> DraftState:
    return change(state, abandoned=True, candidates=(), selected=None, read_at=None,
                  requested_quantity=None, request_notes=None, messages=())


def preview(state: DraftState) -> str:
    import json
    # JSON quoting prevents source text/notes from injecting terminal lines or controls.
    def quoted(value): return json.dumps(value, ensure_ascii=True)
    lines = [WARNING, f"Revision: {state.revision}; status: {state.status}",
             f"User: {state.user.id} / {quoted(state.user.username)} / {quoted(state.user.role)}",
             f"Requested quantity: {state.requested_quantity if state.requested_quantity is not None else 'missing'}",
             f"Notes: {quoted(state.request_notes) if state.request_notes is not None else 'none'}"]
    if state.selected:
        m = state.selected
        lines += [f"Material: {m.id} / {quoted(m.material_code)} / {quoted(m.material_name)}",
                  f"Unit: {quoted(m.unit)}; available: {m.quantity_available}; reserved: {m.quantity_reserved}; unreserved: {m.quantity_unreserved}",
                  f"QC metadata: {quoted(m.qc_status)}; location ID: {m.location_id}; archived: {m.is_archived}",
                  f"Source updated_at: {quoted(m.updated_at)}; read at: {state.read_at}",
                  "Advisory stock sufficient: " + ("unknown" if state.requested_quantity is None else
                      str(state.requested_quantity <= m.quantity_unreserved))]
    else:
        lines.append("Material: not selected")
    if state.has_more:
        lines.append("More matches exist; only the displayed page was read. Refine the search.")
    if state.abandoned:
        lines.append("Draft abandoned.")
    elif state.selected is None:
        if state.search_performed and not state.candidates:
            lines.append(f"No matching source record found. Filters: {state.search_filters}. Revise your search.")
        elif state.candidates:
            lines.append(f"Candidates (revision {state.candidate_revision}; select by source ID):")
            for m in state.candidates:
                lines.append(f"ID {m.id} / {quoted(m.material_code)} / {quoted(m.material_name)}; unit {quoted(m.unit)}; "
                             f"QC {quoted(m.qc_status)}; location {m.location_id}; archived {m.is_archived}; "
                             f"available {m.quantity_available}; reserved {m.quantity_reserved}; unreserved {m.quantity_unreserved}")
            lines.append("Which material ID? Enter /select ID.")
        else:
            lines.append("Which material do you need? Enter /search DESCRIPTION or /material ID_OR_CODE.")
    elif state.selected.is_archived:
        lines.append("Material is archived. Choose another material using /search or /material.")
    elif state.requested_quantity is None:
        lines.append("How many units? Enter /quantity POSITIVE_INTEGER (no unit conversion).")
    elif "sufficient advisory stock" in state.unresolved:
        lines.append("Not ready: requested quantity exceeds current unreserved stock. Edit quantity or material.")
    lines.append("Stock is advisory, not a reservation or guarantee; the backend checks again at submission.")
    return "\n".join(lines)
