import json
from datetime import datetime, timezone, timedelta

import pytest

from lab_workflow_agent.config import AppError
from lab_workflow_agent.draft import DraftSession, DraftInputError
from lab_workflow_agent.order_models import OrderRead
from lab_workflow_agent.source_client import AmbiguousWrite, SourceError
from lab_workflow_agent.source_models import Page
from lab_workflow_agent.submission import Submission, interact_order
from test_draft import FakeSource, FakeProvider, material


def order(**updates):
    fields = dict(id=21, requested_by_user_id=10, material_id=1, requested_quantity=12,
                  reserved_quantity=0, status='submitted', request_notes=None, is_archived=False,
                  created_at=datetime.now(timezone.utc).isoformat())
    fields.update(updates)
    return OrderRead(**fields)


class Source(FakeSource):
    def __init__(self):
        super().__init__()
        self.orders = []
        self.posts = []
        self.error = None
        self.commit = True
        self.overrides = {}
        self.extra = False
        self.huge = False
        self.verify_error = False
        self.stock_after = None
        self.user_override = {}

    def current_user(self):
        return super().current_user().model_copy(update=self.user_override)

    def list_orders(self, *, material_id, page, size):
        self.calls.append(('GET /orders', page))
        if self.huge: return Page[OrderRead](items=[], total=101, page=page, size=size, pages=11)
        return Page[OrderRead](items=self.orders[(page-1)*size:page*size], total=len(self.orders),
                               page=page, size=size, pages=(len(self.orders)+size-1)//size)

    def get_order(self, order_id):
        self.calls.append(('GET /orders/'+str(order_id),None))
        if self.verify_error: raise SourceError('not found',status=404)
        return next(o for o in self.orders if o.id==order_id)

    def create_order(self, payload, *, request_id):
        self.posts.append((payload, request_id))
        result = order(**{**payload.model_dump(), **self.overrides})
        if self.commit:
            self.orders.append(result)
            if self.extra: self.orders.append(order(id=22))
        if self.stock_after is not None: self.items[0].quantity_available=self.stock_after
        if self.error: raise self.error
        return result


def ready():
    source=Source(); session=DraftSession(FakeProvider(),source,'/material 1')
    session.handle('/material 1'); session.handle('/quantity 12')
    action=Submission(session); output=[]; action.show_preview(output.append)
    return action, source, output


def confirm(action):
    return action.confirm('confirm '+action.preview.capability)


def test_preview_binding_and_verified_once():
    action, source, output=ready()
    token=action.preview.capability
    assert 'POST /orders' in output[0] and token in output[0]
    assert action.preview.payload.canonical()=='{"material_id":1,"request_notes":null,"requested_quantity":12}'
    receipt=json.loads(confirm(action))
    assert receipt['outcome']=='succeeded' and receipt['origin']=='response'
    assert receipt['reserved_quantity']==0 and receipt['stock_observation']=='unchanged'
    assert token not in json.dumps(receipt) and token not in repr(action.preview)
    assert len(source.posts)==1
    for _ in range(2):
        with pytest.raises(DraftInputError): action.confirm('confirm '+token)
    with pytest.raises(DraftInputError): action.show_preview(output.append)
    assert len(source.posts)==1


@pytest.mark.parametrize('text',['yes','ok','go ahead','confirm','confirm unknown','/confirm wrong',' confirm wrong'])
def test_no_agreement_or_wrong_capability(text):
    action,source,_=ready()
    with pytest.raises(DraftInputError): action.confirm(text)
    assert len(source.posts)==0


def test_display_must_complete():
    action,source,_=ready()
    def failed(_): raise OSError('terminal closed')
    with pytest.raises(OSError): action.show_preview(failed)
    with pytest.raises(DraftInputError): confirm(action)
    assert len(source.posts)==0


@pytest.mark.parametrize('edit',['/quantity 13','/notes changed','/clear-notes','/material 1','/reset','/abandon'])
def test_draft_edits_invalidate_binding(edit):
    action,source,_=ready(); action.session.handle(edit)
    with pytest.raises(DraftInputError): confirm(action)
    assert action.stage=='invalidated' and len(source.posts)==0


@pytest.mark.parametrize('field,value',[
    ('material_code','changed'),('material_name','changed'),('unit','L'),('qc_status','failed'),
    ('location_id',9),('quantity_available',99),('quantity_reserved',21),('is_archived',True),
    ('updated_at','2026-10-01T12:00:00')])
def test_material_refresh_invalidates(field,value):
    action,source,_=ready(); setattr(source.items[0],field,value)
    assert field in confirm(action)
    assert action.stage=='invalidated' and len(source.posts)==0


@pytest.mark.parametrize('updates',[{'id':11},{'role':'staff'},{'username':'changed'}])
def test_identity_refresh_invalidates(updates):
    action,source,_=ready(); source.user_override=updates
    assert 'user.' in confirm(action)
    assert len(source.posts)==0


def test_missing_material_no_post():
    action,source,_=ready(); source.missing=True
    assert 'No POST' in confirm(action).replace('no POST','No POST')
    assert len(source.posts)==0 and action.stage=='invalidated'


def test_stale_preview_and_cancel():
    action,source,output=ready(); old=action.preview.capability
    action.show_preview(output.append)
    assert old!=action.preview.capability
    with pytest.raises(DraftInputError): action.confirm('confirm '+old)
    action.invalidate()
    with pytest.raises(DraftInputError): action.confirm('confirm '+old)
    assert len(source.posts)==0


@pytest.mark.parametrize('status',[401,403,404,409,422])
def test_deterministic_failure_consumed(status):
    action,source,_=ready(); source.commit=False; source.error=SourceError('rejected',status=status)
    token=action.preview.capability
    assert json.loads(confirm(action))['outcome']=='failed'
    with pytest.raises(DraftInputError): action.confirm('confirm '+token)
    assert len(source.posts)==1


@pytest.mark.parametrize('error',[AmbiguousWrite('timeout'),AmbiguousWrite('lost connection'),AmbiguousWrite('malformed response')])
def test_ambiguous_reconciles_exactly_one(error):
    action,source,_=ready(); source.error=error
    result=json.loads(confirm(action))
    assert result['outcome']=='succeeded' and result['origin']=='reconciliation'
    assert len(source.posts)==1


@pytest.mark.parametrize('kind',['zero','multiple','read_failure','old_timestamp','page_limit'])
def test_ambiguous_stays_unresolved(kind):
    action,source,_=ready(); source.error=AmbiguousWrite('unknown')
    if kind=='zero': source.commit=False
    if kind=='multiple': source.extra=True
    if kind=='read_failure': source.verify_error=True
    if kind=='old_timestamp': source.overrides={'created_at':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()}
    if kind=='page_limit':
        create=source.create_order
        def trigger(*a,**kw):
            source.huge=True
            return create(*a,**kw)
        source.create_order=trigger
    result=json.loads(confirm(action))
    assert result['outcome']=='needs_reconciliation' and len(source.posts)==1


@pytest.mark.parametrize('field,value', [('requested_by_user_id',99),('material_id',2),('requested_quantity',13),
    ('request_notes','wrong'),('status','approved'),('reserved_quantity',12),('is_archived',True)])
def test_wrong_success_never_claimed(field,value):
    action,source,_=ready(); source.overrides={field:value}
    assert json.loads(confirm(action))['outcome']=='needs_reconciliation'
    assert len(source.posts)==1


def test_verification_404_is_ambiguous_not_rejection():
    action,source,_=ready(); source.verify_error=True
    assert json.loads(confirm(action))['outcome']=='needs_reconciliation'
    assert len(source.posts)==1


def test_baseline_bound_stops_write():
    action,source,_=ready(); source.huge=True
    confirm(action)
    assert action.stage=='invalidated' and len(source.posts)==0


def test_complete_baseline_multiple_pages():
    action,source,_=ready(); source.orders=[order(id=i) for i in range(1,12)]
    assert json.loads(confirm(action))['outcome']=='succeeded'
    assert action.baseline==set(range(1,12)) and len(source.posts)==1


def test_stock_difference_not_attributed_to_submission():
    action,source,_=ready(); source.stock_after=70
    result=json.loads(confirm(action))
    assert 'causation is not established' in result['stock_observation']
    assert len(source.posts)==1


def test_readiness_and_injection():
    action,source,_=ready(); action.session.handle('/reset'); action.invalidate()
    with pytest.raises(DraftInputError): action.show_preview(lambda _:None)
    assert len(source.posts)==0


def test_interactive_capability_never_sent_to_model_and_no_duplicate():
    source=Source(); provider=FakeProvider()
    session=DraftSession(provider,source,'/material 1'); output=[]
    steps=iter(['/quantity 12','/preview','leak','yes','confirm','confirm','/exit'])
    token=None
    def emit(value):
        nonlocal token
        output.append(value)
        if 'Preview ID: ' in value: token=value.split('Preview ID: ')[1].splitlines()[0]
    def read(_):
        step=next(steps)
        return ('please show '+token) if step=='leak' else ('confirm '+token) if step=='confirm' else step
    interact_order(session,'/material 1',emit,read)
    assert len(source.posts)==1 and not provider.calls
    assert 'POST attempts: 1' in output[-1] and session.state.abandoned


def test_interactive_model_cannot_confirm():
    source=Source(); provider=FakeProvider({'operation':'confirm','confirm':True})
    session=DraftSession(provider,source,'/material 1'); steps=iter(['please submit','/exit'])
    interact_order(session,'/material 1',lambda _:None,lambda _:next(steps))
    assert len(source.posts)==0


def test_concurrent_confirmation_only_one_post():
    from concurrent.futures import ThreadPoolExecutor
    action,source,_=ready(); command='confirm '+action.preview.capability
    def run():
        try: return action.confirm(command)
        except DraftInputError: return 'blocked'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:run(),range(2)))
    assert 'blocked' in results and len(source.posts)==1


def test_unknown_timestamp_candidate_prevents_false_reconciliation():
    action,source,_=ready(); source.error=AmbiguousWrite('timeout')
    create=source.create_order
    def add(*a,**kw):
        source.orders.append(order(id=22,created_at=None))
        return create(*a,**kw)
    source.create_order=add
    assert json.loads(confirm(action))['outcome']=='needs_reconciliation'
    assert len(source.posts)==1


def test_interruption_after_post_never_allows_reuse():
    action,source,_=ready(); source.error=KeyboardInterrupt(); token=action.preview.capability
    with pytest.raises(KeyboardInterrupt): confirm(action)
    assert action.stage=='needs_reconciliation' and len(source.posts)==1
    with pytest.raises(DraftInputError): action.confirm('confirm '+token)
    assert len(source.posts)==1


def test_order_cli_requires_live(capsys):
    from lab_workflow_agent.cli import main
    assert main(['order','/material 1'])==1
    assert '--live' in capsys.readouterr().err


def test_order_cli_integration_and_cleanup(monkeypatch,capsys):
    from lab_workflow_agent import cli
    monkeypatch.setenv('MOONSHOT_API_KEY','fake-provider-secret')
    monkeypatch.setenv('LAB_STORAGE_BEARER_TOKEN','fake-source-secret')
    source=Source(); provider=FakeProvider(); closed=[]
    source.close=lambda:closed.append('source')
    provider.close=lambda:closed.append('provider')
    monkeypatch.setattr(cli,'LabStorageClient',lambda _:source)
    monkeypatch.setattr(cli,'MoonshotProvider',lambda _:provider)
    commands=iter(['/quantity 12','/notes fake-source-secret','/preview','/cancel','/exit'])
    monkeypatch.setattr('builtins.input',lambda _:next(commands))
    assert cli.main(['order','/material 1','--live'])==0
    output=capsys.readouterr().out
    assert 'fake-source-secret' not in output and 'fake-provider-secret' not in output
    assert 'ACTION PREVIEW' in output and 'No order was created.' not in output.split('discarded')[-1]
    assert closed==['provider','source'] and len(source.posts)==0
