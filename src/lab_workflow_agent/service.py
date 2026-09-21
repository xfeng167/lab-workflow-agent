from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import AppError
from .provider import Completion, Message, Provider


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    intent: Literal["find_material", "unknown"]
    material_query: str | None = Field(min_length=1, max_length=500)
    quantity: int | None = Field(gt=0, le=1_000_000)
    qc_status: Literal["pending", "passed", "failed"] | None


def checked(result: Completion) -> Completion:
    if result.finish_reason == "length":
        raise AppError("Provider output was truncated; no result was accepted.")
    if result.finish_reason != "stop" or not result.content.strip():
        raise AppError("Provider did not return a complete answer.")
    return result


def chat(provider: Provider, prompt: str) -> Completion:
    return checked(provider.complete([Message("user", prompt)]))


def extract_intent(provider: Provider, prompt: str) -> tuple[Intent, Completion]:
    instructions = (
        'Extract the request into a JSON object only, with exactly these fields: '
        'intent ("find_material" or "unknown"), material_query (string or null), '
        'quantity (positive integer or null), qc_status ("pending", "passed", "failed", or null). '
        'Use null for unstated facts. Do not invent inventory facts or execute requests. '
        'Example: {"intent":"find_material","material_query":"control samples",'
        '"quantity":20,"qc_status":"passed"}.'
    )
    result = checked(provider.complete(
        [Message("system", instructions), Message("user", prompt)], structured=True
    ))
    try:
        intent = Intent.model_validate_json(result.content)
    except ValidationError:
        raise AppError("Structured response failed JSON/schema validation; no result was accepted.") from None
    return intent, result
