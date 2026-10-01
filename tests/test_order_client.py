import json
import httpx
import pytest
from pydantic import ValidationError
from lab_workflow_agent.config import AppError
from lab_workflow_agent.order_models import OrderCreate
from lab_workflow_agent.source_client import LabStorageClient, SourceError, AmbiguousWrite
from test_source_client import settings, TOKEN
from test_submission import order


def test_single_post_exact_payload_and_headers():
    calls=[]
    def handler(request):
        calls.append(request)
        assert request.method=='POST' and request.url.path=='/orders'
        assert request.headers['Authorization']=='Bearer '+TOKEN
        assert request.headers['X-Request-ID']=='a'*32
        assert json.loads(request.content)==dict(material_id=1,requested_quantity=12,request_notes='test')
        return httpx.Response(201,json=order(request_notes='test').model_dump())
    with LabStorageClient(settings(),transport=httpx.MockTransport(handler)) as client:
        result=client.create_order(OrderCreate(material_id=1,requested_quantity=12,request_notes='  test  '),request_id='a'*32)
    assert result.id==21 and len(calls)==1


@pytest.mark.parametrize('status,code,ambiguous',[(401,'AUTH_TOKEN_INVALID',False),(403,'PERMISSION_DENIED',False),
    (404,'MATERIAL_NOT_FOUND',False),(409,'MATERIAL_ARCHIVED',False),(409,'ORDER_STOCK_INSUFFICIENT',False),
    (422,'VALIDATION_ERROR',False),(409,'UNKNOWN',True),(500,'INTERNAL_ERROR',True),(302,None,True),
    (200,None,True),(201,None,True)])
def test_response_classification_never_retries(status,code,ambiguous):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(status,json={'error':{'code':code,'message':TOKEN}},headers={'Location':'https://example.com'})
    with LabStorageClient(settings(),transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError) as exc:
            client.create_order(OrderCreate(material_id=1,requested_quantity=12),request_id='a'*32)
    assert isinstance(exc.value,AmbiguousWrite)==ambiguous
    assert TOKEN not in str(exc.value) and len(calls)==1


@pytest.mark.parametrize('error',[httpx.ReadTimeout,httpx.ConnectError,httpx.RemoteProtocolError])
def test_transport_loss_is_ambiguous_one_attempt(error):
    calls=[]
    def handler(request):
        calls.append(request); raise error(TOKEN,request=request)
    with LabStorageClient(settings(),transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AmbiguousWrite):
            client.create_order(OrderCreate(material_id=1,requested_quantity=12),request_id='a'*32)
    assert len(calls)==1


def test_raw_arguments_and_bad_request_id_no_post():
    with LabStorageClient(settings(),transport=httpx.MockTransport(lambda _:pytest.fail('unexpected network'))) as client:
        with pytest.raises(AppError): client.create_order({'material_id':1},request_id='a'*32)
        with pytest.raises(AppError): client.create_order(OrderCreate(material_id=1,requested_quantity=12),request_id='bad')


@pytest.mark.parametrize('value',[True,0,-1,'12',1.5,1_000_001])
def test_invalid_create_quantity(value):
    with pytest.raises(ValidationError): OrderCreate(material_id=1,requested_quantity=value)


def test_order_get_list_contract():
    calls=[]
    def handler(request):
        calls.append(request)
        assert request.method=='GET'
        if request.url.path=='/orders/21': return httpx.Response(200,json=order().model_dump())
        assert request.url.params['include_archived']=='true'
        assert request.url.params['material_id']=='1'
        return httpx.Response(200,json=dict(items=[order().model_dump()],page=1,size=10,total=1,pages=1))
    with LabStorageClient(settings(),transport=httpx.MockTransport(handler)) as client:
        assert client.get_order(21).id==21
        assert client.list_orders(material_id=1).total==1
    assert len(calls)==2


def test_no_other_write_tools():
    from lab_workflow_agent.tools import tool_definitions
    assert all('order' not in json.dumps(item).lower() for item in tool_definitions())
    assert not any(hasattr(LabStorageClient,name) for name in ('approve_order','reject_order','fulfill_order','cancel_order','archive_order'))
