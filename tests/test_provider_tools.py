import json

import httpx
import pytest

from lab_workflow_agent.config import AppError, Settings
from lab_workflow_agent.provider import Message, MoonshotProvider, ToolCall


def call(id="call-1"):
    return {"id": id, "type": "function", "function": {
        "name": "get_material", "arguments": '{"material_id":12}'}}


def response(finish="tool_calls", calls=None, content=None):
    return {"id": "completion-1", "object": "chat.completion", "created": 0,
        "model": "fake-model", "choices": [{"index": 0, "finish_reason": finish,
        "message": {"role": "assistant", "content": content,
                    "tool_calls": [call()] if calls is None else calls}}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}}


def test_complete_tool_roundtrip():
    requests = []
    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["tool_choice"] == "auto"
        assert len(body["tools"]) == 4
        assert "fake-provider-secret" not in request.content.decode()
        if len(requests) == 1:
            data = response(calls=[call(), call("call-2")])
            data["choices"][0]["message"]["reasoning_content"] = "preserved metadata"
            return httpx.Response(200, json=data)
        history = body["messages"]
        assert history[1]["tool_calls"] == [call(), call("call-2")]
        assert history[1]["reasoning_content"] == "preserved metadata"
        assert [item["tool_call_id"] for item in history[2:]] == ["call-1", "call-2"]
        return httpx.Response(200, json=response("stop", [], "Material 12 has 75 mL unreserved."))
    provider = MoonshotProvider(Settings(api_key="fake-provider-secret"), transport=httpx.MockTransport(handler))
    try:
        history = [Message("user", "Find material 12")]
        first = provider.complete_tools(history)
        assert first.tool_calls[0].arguments == '{"material_id":12}'
        history += [first.as_message(), Message("tool", '{}', tool_call_id="call-1"),
                    Message("tool", '{}', tool_call_id="call-2")]
        final = provider.complete_tools(history)
        assert final.finish_reason == "stop" and final.usage["total_tokens"] == 5
        assert not final.tool_calls
    finally:
        provider.close()
    assert len(requests) == 2


@pytest.mark.parametrize("finish,calls,content", [
    ("stop", [call()], "text"), ("length", [], "partial"),
    ("content_filter", [], "text"), ("unexpected", [], "text"),
    ("tool_calls", [], None), ("stop", [], " "),
    ("tool_calls", [call(), call()], None),
    ("tool_calls", [dict(call(), id="")], None),
    ("tool_calls", [{"type":"function", "function":call()["function"]}], None),
    ("tool_calls", [dict(call(), function={"name":"", "arguments":"{}"})], None),
    ("tool_calls", [dict(call(), function={"name":"get_material", "arguments":{}})], None),
    ("tool_calls", [dict(call(), type="custom")], None),
])
def test_malformed_tool_responses(finish, calls, content):
    provider = MoonshotProvider(Settings(api_key="fake"), transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=response(finish, calls, content))))
    try:
        with pytest.raises(AppError):
            provider.complete_tools([Message("user", "test")])
    finally:
        provider.close()


@pytest.mark.parametrize("history", [
    [Message("tool", "{}", tool_call_id="unknown")],
    [Message("assistant", None, (ToolCall("a", "get_material", "{}"),))],
    [Message("user", "test", (ToolCall("a", "get_material", "{}"),))],
    [Message("assistant", None, (ToolCall("a", "get_material", "{}"),)), Message("user", "next")],
    [Message("assistant", None, (ToolCall("a", "get_material", "{}"),)),
     Message("tool", "{}", tool_call_id="a"), Message("tool", "{}", tool_call_id="a")],
])
def test_bad_history_no_network(history):
    provider = MoonshotProvider(Settings(api_key="fake"), transport=httpx.MockTransport(
        lambda _: pytest.fail("Invalid history sent to provider")))
    try:
        with pytest.raises(AppError):
            provider.complete_tools(history)
    finally:
        provider.close()
