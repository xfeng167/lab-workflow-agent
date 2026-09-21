import json

import httpx
import pytest

from lab_workflow_agent import cli
from lab_workflow_agent.config import AppError, Settings, load_settings
from lab_workflow_agent.provider import Completion, Message, MoonshotProvider
from lab_workflow_agent.service import chat, extract_intent

KEY = "fake-unit-test-secret"
VALID = '{"intent":"find_material","material_query":"control samples","quantity":20,"qc_status":"passed"}'


class FakeProvider:
    def __init__(self, content=VALID, finish="stop"):
        self.result = Completion(content, "fake-model", finish, {"total_tokens": 10})
        self.calls = []

    def complete(self, messages, *, structured=False):
        self.calls.append((messages, structured))
        return self.result

    def models(self):
        self.calls.append("models")
        return ["kimi-k2.6"]

    def close(self):
        pass


def configured(monkeypatch):
    monkeypatch.setenv("MOONSHOT_API_KEY", KEY)


def test_valid_configuration_and_redaction(monkeypatch):
    configured(monkeypatch)
    settings = load_settings()
    assert settings.max_completion_tokens == 300
    assert settings.base_url == "https://api.moonshot.ai/v1"
    assert KEY not in repr(settings)
    assert KEY not in settings.model_dump_json()


@pytest.mark.parametrize("value", [None, "", "  "])
def test_missing_key(monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("MOONSHOT_API_KEY", value)
    with pytest.raises(AppError, match="api_key"):
        load_settings()


@pytest.mark.parametrize("field,value", [("MAX_COMPLETION_TOKENS", "0"), ("MAX_COMPLETION_TOKENS", "301"),
    ("MAX_COMPLETION_TOKENS", "no"), ("BASE_URL", "https://api.moonshot.cn/v1"),
    ("BASE_URL", "https://example.com"), ("MODEL", ""), ("THINKING", "invalid")])
def test_invalid_configuration(monkeypatch, field, value):
    configured(monkeypatch)
    monkeypatch.setenv("MOONSHOT_" + field, value)
    with pytest.raises(AppError) as err:
        load_settings()
    assert KEY not in str(err.value)


def test_doctor_offline(monkeypatch, capsys):
    configured(monkeypatch)
    def forbidden(*args):
        pytest.fail("doctor constructed a provider")
    monkeypatch.setattr(cli, "MoonshotProvider", forbidden)
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert KEY not in out
    assert json.loads(out)["network"] == "not used"


def test_doctor_missing_key(capsys):
    assert cli.main(["doctor"]) == 1
    assert "api_key" in capsys.readouterr().err


@pytest.mark.parametrize("command", [["models"], ["chat", "hello"], ["extract-intent", "sample"], ["smoke"]])
def test_live_commands_need_opt_in(command, capsys):
    assert cli.main(command) == 1
    assert "--live" in capsys.readouterr().err


def test_plain_text():
    fake = FakeProvider("An API connects programs.")
    assert chat(fake, "Explain an API").content == "An API connects programs."
    assert fake.calls[0][1] is False


def test_structured_success():
    fake = FakeProvider()
    intent, result = extract_intent(fake, "Find twenty passed control samples")
    assert intent.quantity == 20 and intent.qc_status == "passed"
    assert fake.calls[0][1] is True
    assert result.usage["total_tokens"] == 10


@pytest.mark.parametrize("content", ["not json", "{}", "[]", VALID.replace('20', '0'),
    VALID.replace('20', 'true'), VALID.replace('20', '"20"'), VALID.replace('passed', 'invented'),
    VALID[:-1] + ',"execute":true}', VALID.replace('control samples', '   ')])
def test_bad_structured_output(content):
    with pytest.raises(AppError, match="validation"):
        extract_intent(FakeProvider(content), "find samples")


@pytest.mark.parametrize("finish", ["length", "tool_calls", "content_filter"])
def test_incomplete_output(finish):
    fake = FakeProvider(VALID, finish)
    with pytest.raises(AppError):
        chat(fake, "hello")
    with pytest.raises(AppError):
        extract_intent(fake, "find")


def test_empty_output():
    with pytest.raises(AppError):
        chat(FakeProvider(""), "hello")


@pytest.mark.parametrize("status,expected", [(401, "authentication"), (402, "balance"), (403, "denied"),
    (429, "rate limit"), (500, "unavailable"), (400, "rejected"), (302, "rejected")])
def test_sdk_status_mapping_and_no_retries(status, expected):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": KEY}}, headers={"Location": "https://example.com"})
    provider = MoonshotProvider(Settings(api_key=KEY), transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(AppError) as err:
            provider.models()
        assert expected in str(err.value)
        assert KEY not in str(err.value)
        assert len(calls) == 1
    finally:
        provider.close()


@pytest.mark.parametrize("kind,expected", [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "unavailable")])
def test_sdk_connection_mapping(kind, expected):
    calls = []
    def handler(request):
        calls.append(request)
        raise kind(KEY, request=request)
    provider = MoonshotProvider(Settings(api_key=KEY), transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(AppError) as err:
            provider.complete([Message("user", "hello")])
        assert expected in str(err.value) and KEY not in str(err.value)
        assert len(calls) == 1
    finally:
        provider.close()


def test_adapter_payload_and_metadata():
    def handler(request):
        body = json.loads(request.content)
        assert body["max_completion_tokens"] == 300
        assert body["response_format"] == {"type": "json_object"}
        assert body["thinking"] == {"type": "disabled"}
        assert KEY not in request.content.decode()
        return httpx.Response(200, json={"id": "fake", "object": "chat.completion", "created": 0,
            "model": "fake-model", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": VALID}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}})
    provider = MoonshotProvider(Settings(api_key=KEY), transport=httpx.MockTransport(handler))
    try:
        result = provider.complete([Message("user", "find")], structured=True)
        assert result.model == "fake-model" and result.usage["total_tokens"] == 5
    finally:
        provider.close()


def test_cli_redacts_provider_echo(monkeypatch, capsys):
    configured(monkeypatch)
    monkeypatch.setattr(cli, "MoonshotProvider", lambda _: FakeProvider(KEY))
    assert cli.main(["chat", "hi", "--live"]) == 0
    out = capsys.readouterr().out
    assert KEY not in out and "[REDACTED]" in out


def test_smoke_three_requests(monkeypatch, capsys):
    configured(monkeypatch)
    fake = FakeProvider()
    monkeypatch.setattr(cli, "MoonshotProvider", lambda _: fake)
    assert cli.main(["smoke", "--live"]) == 0
    assert len(fake.calls) == 3
    assert '"requests_completed": 3' in capsys.readouterr().out


def test_smoke_stops_on_unlisted_model(monkeypatch, capsys):
    configured(monkeypatch)
    monkeypatch.setenv("MOONSHOT_MODEL", "unavailable")
    fake = FakeProvider()
    monkeypatch.setattr(cli, "MoonshotProvider", lambda _: fake)
    assert cli.main(["smoke", "--live"]) == 1
    assert fake.calls == ["models"]


def test_smoke_stops_on_truncation(monkeypatch, capsys):
    configured(monkeypatch)
    fake = FakeProvider(finish="length")
    monkeypatch.setattr(cli, "MoonshotProvider", lambda _: fake)
    assert cli.main(["smoke", "--live"]) == 1
    assert len(fake.calls) == 2


def test_malformed_provider_response():
    provider = MoonshotProvider(Settings(api_key=KEY), transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"choices": [], "model": "fake"})))
    try:
        with pytest.raises(AppError, match="invalid response"):
            provider.complete([Message("user", "hello")])
    finally:
        provider.close()


def test_cli_blocks_sdk_child_logging(monkeypatch, capsys):
    import logging
    configured(monkeypatch)
    fake = FakeProvider("hello")
    def factory(_):
        logging.getLogger("openai._base_client").warning(KEY)
        logging.getLogger("httpcore.connection").warning(KEY)
        return fake
    monkeypatch.setattr(cli, "MoonshotProvider", factory)
    assert cli.main(["chat", "hi", "--live"]) == 0
    captured = capsys.readouterr()
    assert KEY not in captured.out + captured.err
