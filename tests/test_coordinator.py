import json

import pytest

from lab_workflow_agent.config import AppError
from lab_workflow_agent.coordinator import ask
from lab_workflow_agent.provider import Completion, ToolCall
from test_tools import FakeSource


class Provider:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.history = []

    def complete_tools(self, history):
        self.history.append(list(history))
        return next(self.responses)


def calls(*ids):
    return Completion("", "fake", "tool_calls", tool_calls=tuple(
        ToolCall(i, "get_material", '{"material_id":12}') for i in ids))


def final(content=None):
    return Completion(content or '{"material_ids":[12],"location_ids":[]}', "fake", "stop")


def test_grounded_roundtrip():
    provider = Provider([calls("a", "b"), final()])
    result = ask(provider, FakeSource(), "stock?")
    assert result.model_responses == 2 and result.source_tool_calls == 2
    assert "unreserved: 75 mL" in result.answer
    assert "TEST-12" in result.answer
    assert [m.tool_call_id for m in provider.history[1] if m.role == "tool"] == ["a", "b"]


@pytest.mark.parametrize("responses", [
    [final()], [calls("a", "a")], [calls("a", "b", "c", "d")],
    [calls("a"), calls("a")],
    [calls("a"), calls("b"), calls("c"), calls("d")],
    [calls("a", "b", "c"), calls("d", "e", "f"), calls("g")],
    [Completion("", "fake", "length")],
    [calls("a"), final('{"material_ids":[999],"location_ids":[]}')] ,
    [calls("a"), final("An order was created.")],
    [calls("a"), final('{"material_ids":[],"location_ids":[]}')],
])
def test_limits_and_invalid_answers(responses):
    with pytest.raises(AppError):
        ask(Provider(responses), FakeSource(), "stock?")


def test_invalid_batch_does_not_execute_first_call():
    response = calls("a")
    bad = Completion("", "fake", "tool_calls", tool_calls=response.tool_calls + (
        ToolCall("b", "write_order", "{}"),))
    source = FakeSource()
    with pytest.raises(AppError):
        ask(Provider([bad]), source, "stock?")
    assert not source.calls


def test_partial_results():
    response = Completion("", "fake", "tool_calls", tool_calls=(ToolCall("a", "search_materials", "{}"),))
    answer = ask(Provider([response, final()]), FakeSource(), "buffers?")
    assert "more pages" in answer.answer


def test_source_instructions_do_not_dispatch():
    response = Completion("", "fake", "tool_calls", tool_calls=(ToolCall("a", "get_location", '{"location_id":3}'),))
    source = FakeSource()
    answer = ask(Provider([response, final('{"material_ids":[],"location_ids":[3]}')]), source, "location?")
    assert source.calls == [("get_location", 3)]
    assert "delete_material" not in answer.answer
