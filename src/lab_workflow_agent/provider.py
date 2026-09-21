from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from .config import AppError, Settings


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class Completion:
    content: str
    model: str
    finish_reason: str
    usage: dict[str, int | None] | None = None


class Provider(Protocol):
    def models(self) -> list[str]: ...
    def complete(self, messages: list[Message], *, structured: bool = False) -> Completion: ...


def provider_error(exc: Exception) -> AppError:
    if isinstance(exc, APITimeoutError):
        return AppError("Provider timeout. No automatic retry was attempted.")
    if isinstance(exc, APIConnectionError):
        return AppError("Provider unavailable. Check connectivity; no automatic retry was attempted.")
    if isinstance(exc, APIStatusError):
        messages = {
            401: "Provider authentication failed. Check the international API key.",
            402: "Provider balance is insufficient. Check the platform account.",
            403: "Provider denied access. Check account permissions and balance.",
            429: "Provider rate limit reached. Stop and check quota before retrying.",
        }
        if exc.status_code in messages:
            return AppError(messages[exc.status_code])
        if exc.status_code >= 500:
            return AppError("Provider unavailable. No automatic retry was attempted.")
        return AppError("Provider rejected the request. Check the configured model and parameters.")
    return AppError("Provider returned an invalid response.")


class MoonshotProvider:
    """Only this adapter knows the SDK. Credentials never enter model messages."""

    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self._client = OpenAI(
            api_key=settings.api_key.get_secret_value(),
            base_url=settings.base_url,
            max_retries=0,
            timeout=30.0,
            http_client=httpx.Client(transport=transport, follow_redirects=False, trust_env=False),
        )

    def close(self) -> None:
        self._client.close()

    def models(self) -> list[str]:
        try:
            # Read one response only: do not auto-paginate or retry.
            return sorted(model.id for model in self._client.models.list().data)
        except Exception as exc:
            raise provider_error(exc) from None

    def complete(self, messages: list[Message], *, structured: bool = False) -> Completion:
        try:
            extra = {} if self.settings.thinking == "omit" else {
                "thinking": {"type": self.settings.thinking}
            }
            response = self._client.chat.completions.create(
                model=self.settings.model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                max_completion_tokens=self.settings.max_completion_tokens,
                response_format={"type": "json_object" if structured else "text"},
                extra_body=extra,
            )
            choice = response.choices[0]
            if choice.message.tool_calls or choice.message.refusal:
                raise AppError("Provider did not return the requested completion.")
            usage = None if response.usage is None else {
                key: getattr(response.usage, key)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            }
            return Completion(choice.message.content or "", response.model, choice.finish_reason, usage)
        except AppError:
            raise
        except Exception as exc:
            raise provider_error(exc) from None
