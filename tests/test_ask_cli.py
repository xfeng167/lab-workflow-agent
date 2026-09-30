import pytest
from lab_workflow_agent import cli
from lab_workflow_agent.config import AppError
from lab_workflow_agent.coordinator import Answer


def test_ask_requires_live(capsys):
    assert cli.main(["ask", "stock?"]) == 1
    assert "--live" in capsys.readouterr().err


def test_ask_validates_both_settings_before_clients(monkeypatch):
    monkeypatch.setenv("MOONSHOT_API_KEY", "fake")
    monkeypatch.setattr(cli, "MoonshotProvider", lambda _: pytest.fail("provider created"))
    monkeypatch.setattr(cli, "LabStorageClient", lambda _: pytest.fail("source created"))
    assert cli.main(["ask", "stock?", "--live"]) == 1


@pytest.mark.parametrize("failure", [None, AppError("Source unavailable"), KeyboardInterrupt()])
def test_ask_cleanup_and_redaction(monkeypatch, capsys, failure):
    monkeypatch.setenv("MOONSHOT_API_KEY", "fake-provider")
    monkeypatch.setenv("LAB_STORAGE_BEARER_TOKEN", "fake-source")
    closed = []
    class Client:
        def __init__(self, name): self.name = name
        def close(self): closed.append(self.name)
    monkeypatch.setattr(cli, "MoonshotProvider", lambda _: Client("provider"))
    monkeypatch.setattr(cli, "LabStorageClient", lambda _: Client("source"))
    def run(*args, **kwargs):
        if failure: raise failure
        return Answer("fake-provider fake-source", 2, 1)
    monkeypatch.setattr(cli, "ask", run)
    code = cli.main(["ask", "stock?", "--live"])
    assert code == (130 if isinstance(failure, KeyboardInterrupt) else 1 if failure else 0)
    assert closed == ["provider", "source"]
    output = capsys.readouterr()
    assert "fake-source" not in output.out and "fake-provider" not in output.out
