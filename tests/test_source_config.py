import json

import pytest

from lab_workflow_agent import cli
from lab_workflow_agent.config import AppError, load_source_settings


TOKEN = "fake-source-test-secret"


def test_source_defaults_without_moonshot_settings():
    settings = load_source_settings()
    assert settings.api_url == "http://127.0.0.1:8000"
    assert settings.timeout_seconds == 10
    assert not settings.token_present


@pytest.mark.parametrize("token", [None, "", "   "])
def test_token_required_only_when_requested(monkeypatch, token):
    if token is not None:
        monkeypatch.setenv("LAB_STORAGE_BEARER_TOKEN", token)
    assert not load_source_settings().token_present
    with pytest.raises(AppError, match="token is required"):
        load_source_settings(require_token=True)


def test_source_secret_redaction(monkeypatch):
    monkeypatch.setenv("LAB_STORAGE_BEARER_TOKEN", TOKEN)
    settings = load_source_settings(require_token=True)
    assert settings.token_present
    assert TOKEN not in repr(settings)
    assert TOKEN not in settings.model_dump_json()


@pytest.mark.parametrize("url", [
    "http://localhost:8000", "https://127.0.0.1:8000",
    "http://example.com:8000", "http://127.0.0.1:8001",
    "http://127.0.0.1:8000/", "http://127.0.0.1:8000/api",
    "http://127.0.0.1:8000?token=" + TOKEN,
    "http://127.0.0.1:8000#fragment",
    "http://user:" + TOKEN + "@127.0.0.1:8000",
])
def test_rejects_nonexact_source_url(monkeypatch, url):
    monkeypatch.setenv("LAB_STORAGE_API_URL", url)
    with pytest.raises(AppError, match="api_url") as error:
        load_source_settings()
    assert TOKEN not in str(error.value)
    assert url not in str(error.value)


@pytest.mark.parametrize("timeout", ["0", "-1", "61", "nan", "inf", "-inf", TOKEN])
def test_invalid_timeout_is_safe(monkeypatch, timeout):
    monkeypatch.setenv("LAB_STORAGE_TIMEOUT_SECONDS", timeout)
    with pytest.raises(AppError, match="timeout_seconds") as error:
        load_source_settings()
    assert TOKEN not in str(error.value)


@pytest.mark.parametrize("timeout", ["0.5", "60"])
def test_valid_timeout(monkeypatch, timeout):
    monkeypatch.setenv("LAB_STORAGE_TIMEOUT_SECONDS", timeout)
    assert load_source_settings().timeout_seconds == float(timeout)


@pytest.mark.parametrize("token", ["", TOKEN])
def test_doctor_source_status_without_client(monkeypatch, capsys, token):
    monkeypatch.setenv("MOONSHOT_API_KEY", "fake-provider-secret")
    monkeypatch.setenv("LAB_STORAGE_BEARER_TOKEN", token)
    monkeypatch.setattr(cli, "MoonshotProvider", lambda _: pytest.fail("Network client constructed"))
    assert cli.main(["doctor"]) == 0
    output = capsys.readouterr().out
    source = json.loads(output)["source"]
    assert source == {"api_url": "http://127.0.0.1:8000", "timeout_seconds": 10,
                      "bearer_token": "present" if token else "missing"}
    assert TOKEN not in output
    assert "fake-provider-secret" not in output


def test_doctor_rejects_invalid_source_without_client(monkeypatch, capsys):
    monkeypatch.setenv("MOONSHOT_API_KEY", "fake-provider-secret")
    monkeypatch.setenv("LAB_STORAGE_API_URL", "http://" + TOKEN + "@example.com")
    monkeypatch.setattr(cli, "MoonshotProvider", lambda _: pytest.fail("Network client constructed"))
    assert cli.main(["doctor"]) == 1
    output = capsys.readouterr()
    assert "api_url" in output.err
    assert TOKEN not in output.out + output.err


def test_moonshot_command_ignores_source_settings(monkeypatch, capsys):
    monkeypatch.setenv("MOONSHOT_API_KEY", "fake-provider-secret")
    monkeypatch.setenv("LAB_STORAGE_API_URL", "invalid")
    monkeypatch.setenv("LAB_STORAGE_TIMEOUT_SECONDS", "invalid")

    class FakeProvider:
        def models(self):
            return ["fake-model"]

        def close(self):
            pass

    monkeypatch.setattr(cli, "MoonshotProvider", lambda _: FakeProvider())
    assert cli.main(["models", "--live"]) == 0
    assert "fake-model" in capsys.readouterr().out
