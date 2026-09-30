from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from .config import AppError, Settings


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    reasoning_content: str | None = None


@dataclass(frozen=True)
class Completion:
    content: str
    model: str
    finish_reason: str
    usage: dict[str, int | None] | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    reasoning_content: str | None = None

    def as_message(self) -> Message:
        return Message("assistant", self.content, self.tool_calls,
                       reasoning_content=self.reasoning_content)


class Provider(Protocol):
    def models(self) -> list[str]: ...
    def complete(self, messages: list[Message], *, structured: bool = False) -> Completion: ...
    def complete_tools(self, messages: list[Message]) -> Completion: ...


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


    def complete_tools(self, messages: list[Message]) -> Completion:
        """One tool-capable response. Execution and loop limits belong to the coordinator."""
        from .tools import tool_definitions

        payload = serialize_tool_history(messages)
        try:
            extra = {} if self.settings.thinking == "omit" else {
                "thinking": {"type": self.settings.thinking}
            }
            response = self._client.chat.completions.create(
                model=self.settings.model, messages=payload,
                tools=tool_definitions(), tool_choice="auto",
                max_completion_tokens=self.settings.max_completion_tokens,
                extra_body=extra,
            )
            if len(response.choices) != 1:
                raise AppError("Provider returned an invalid tool response.")
            choice = response.choices[0]
            message = choice.message
            if message.role != "assistant" or message.refusal:
                raise AppError("Provider did not return the requested tool response.")
            calls = []
            for call in message.tool_calls or []:
                if call.type != "function":
                    raise AppError("Provider returned an unsupported tool type.")
                calls.append(ToolCall(call.id, call.function.name, call.function.arguments))
            validate_tool_calls(calls)
            content = message.content
            if content is not None and not isinstance(content, str):
                raise AppError("Provider returned invalid content.")
            if choice.finish_reason == "tool_calls":
                if not calls:
                    raise AppError("Provider requested tools without tool calls.")
            elif choice.finish_reason == "stop":
                if calls or not content or not content.strip():
                    raise AppError("Provider returned an invalid final tool response.")
            else:
                raise AppError("Provider tool response was incomplete or unsupported.")
            reasoning = getattr(message, "reasoning_content", None)
            if reasoning is not None and not isinstance(reasoning, str):
                raise AppError("Provider returned invalid reasoning metadata.")
            usage = None
            if response.usage is not None:
                usage = {key: getattr(response.usage, key) for key in
                         ("prompt_tokens", "completion_tokens", "total_tokens")}
                if any(value is not None and (type(value) is not int or value < 0)
                       for value in usage.values()):
                    raise AppError("Provider returned invalid usage metadata.")
            return Completion(content or "", response.model, choice.finish_reason,
                              usage, tuple(calls), reasoning)
        except AppError:
            raise
        except Exception as exc:
            raise provider_error(exc) from None


def validate_tool_calls(calls) -> None:
    seen = set()
    for call in calls:
        if (not isinstance(call.id, str) or not call.id.strip()
                or not isinstance(call.name, str) or not call.name.strip()
                or not isinstance(call.arguments, str) or call.id in seen):
            raise AppError("Invalid or duplicate tool-call fields.")
        seen.add(call.id)


def serialize_tool_history(messages: list[Message]) -> list[dict]:
    result = []
    pending = set()
    seen = set()
    for message in messages:
        if message.role not in ("system", "user", "assistant", "tool"):
            raise AppError("Unsupported message role.")
        if message.content is not None and not isinstance(message.content, str):
            raise AppError("Invalid message content.")
        if message.reasoning_content is not None and (
                message.role != "assistant" or not isinstance(message.reasoning_content, str)):
            raise AppError("Invalid assistant reasoning field.")
        item = {"role": message.role, "content": message.content}
        if message.role == "tool":
            if (message.tool_calls or message.tool_call_id not in pending
                    or not isinstance(message.content, str)):
                raise AppError("Tool result has no matching pending call.")
            pending.remove(message.tool_call_id)
            item["tool_call_id"] = message.tool_call_id
        else:
            if pending or message.tool_call_id is not None:
                raise AppError("Tool history is missing matching results.")
            if message.tool_calls:
                if message.role != "assistant":
                    raise AppError("Only assistant messages may request tools.")
                validate_tool_calls(message.tool_calls)
                for call in message.tool_calls:
                    if call.id in seen:
                        raise AppError("Duplicate tool-call ID in history.")
                    seen.add(call.id)
                    pending.add(call.id)
                item["tool_calls"] = [{"id": call.id, "type": "function", "function": {
                    "name": call.name, "arguments": call.arguments}} for call in message.tool_calls]
            elif not isinstance(message.content, str):
                raise AppError("Text messages require content.")
            if message.reasoning_content is not None:
                item["reasoning_content"] = message.reasoning_content
        result.append(item)
    if pending:
        raise AppError("Tool history is missing matching results.")
    return result
