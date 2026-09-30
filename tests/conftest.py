import socket

import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    """No real credentials, dotenv, or network in the default suite."""
    import os
    for name in list(os.environ):
        if name.startswith(("MOONSHOT_", "LAB_STORAGE_")):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    def denied(*args, **kwargs):
        raise AssertionError("Network is forbidden in unit tests")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
