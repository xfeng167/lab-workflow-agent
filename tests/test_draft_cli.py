import pytest

from lab_workflow_agent import cli
from lab_workflow_agent.config import AppError
from test_draft import FakeProvider, FakeSource


def test_draft_requires_explicit_live(capsys):
    assert cli.main(['draft', 'need buffer']) == 1
    assert '--live' in capsys.readouterr().err


def test_draft_configs_checked_before_clients(monkeypatch):
    monkeypatch.setenv('MOONSHOT_API_KEY', 'fake-key')
    monkeypatch.setattr(cli, 'LabStorageClient', lambda _: pytest.fail('source created'))
    monkeypatch.setattr(cli, 'MoonshotProvider', lambda _: pytest.fail('provider created'))
    assert cli.main(['draft','need buffer','--live']) == 1


@pytest.mark.parametrize('ending', ['exit','eof','interrupt','provider_failure'])
def test_draft_cli_cleanup_and_no_writes(monkeypatch, capsys, ending):
    monkeypatch.setenv('MOONSHOT_API_KEY', 'fake-provider-secret')
    monkeypatch.setenv('LAB_STORAGE_BEARER_TOKEN', 'fake-source-secret')
    source = FakeSource()
    source.items[0].material_name = 'fake-source-secret'
    provider = FakeProvider({'operation':'search','query':'buffer'}, AppError('Provider unavailable.'))
    closed=[]
    source.close=lambda: closed.append('source')
    provider.close=lambda: closed.append('provider')
    monkeypatch.setattr(cli,'LabStorageClient', lambda _:source)
    monkeypatch.setattr(cli,'MoonshotProvider', lambda _:provider)
    messages=iter(['/select 1','/quantity 12','/notes fake-provider-secret','/show'])
    def read(_):
        try: return next(messages)
        except StopIteration:
            if ending=='eof': raise EOFError
            if ending=='interrupt': raise KeyboardInterrupt
            if ending=='provider_failure': return 'change this naturally'
            return '/exit'
    monkeypatch.setattr('builtins.input',read)
    result=cli.main(['draft','find a buffer','--live'])
    output=capsys.readouterr()
    assert result == (130 if ending=='interrupt' else 1 if ending=='provider_failure' else 0)
    assert 'draft discarded' in output.out
    assert 'fake-provider-secret' not in output.out
    assert 'fake-source-secret' not in output.out
    assert closed==['provider','source']
    assert all(method.startswith('GET ') for method,_ in source.calls)
