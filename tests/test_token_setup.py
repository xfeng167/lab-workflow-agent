import importlib.util
from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values

spec = importlib.util.spec_from_file_location("token_setup", Path(__file__).resolve().parents[1] / "scripts/configure_local_token.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def test_login_local_only():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.method == "POST"
        assert str(request.url) == "http://127.0.0.1:8000/users/login"
        return httpx.Response(200, json={"token": "fake-token"})
    assert setup.login("viewer", "fake-password", transport=httpx.MockTransport(handler)) == "fake-token"
    assert len(calls) == 1


@pytest.mark.parametrize("status", [401, 429, 302, 500])
def test_login_errors_are_safe_and_not_retried(status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="sensitive", headers={"Location": "https://example.com"})
    with pytest.raises(setup.SetupError) as error:
        setup.login("viewer", "secret", transport=httpx.MockTransport(handler))
    assert "sensitive" not in str(error.value)
    assert len(calls) == 1


def test_save_preserves_other_settings_and_restricts_permissions(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "check_destination", lambda _: None)
    path = tmp_path / ".env"
    path.write_text("MOONSHOT_API_KEY='fake-key'\nLAB_STORAGE_BEARER_TOKEN='old'\n")
    setup.save_token(tmp_path, "new-fake-token")
    data = dotenv_values(path)
    assert data["MOONSHOT_API_KEY"] == "fake-key"
    assert data["LAB_STORAGE_BEARER_TOKEN"] == "new-fake-token"
    assert path.stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".local-token-*"))


def test_symlink_rejected(tmp_path):
    (tmp_path / ".env").symlink_to(tmp_path / "other")
    with pytest.raises(setup.SetupError):
        setup.check_destination(tmp_path)
