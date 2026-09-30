import httpx
import pytest

from lab_workflow_agent.config import AppError, SourceSettings
from lab_workflow_agent.source_client import LabStorageClient, SourceError

TOKEN = "fake-client-secret"


def payload():
    return dict(id=12, material_code="TEST-12", material_name="Buffer",
                material_type="buffer", quantity_available=100, quantity_reserved=25,
                unit="mL", minimum_quantity=10, availability_status="available",
                qc_status="passed", location_id=None, is_archived=False)


def settings():
    return SourceSettings(bearer_token=TOKEN, timeout_seconds=7)


class Transport(httpx.MockTransport):
    closed = False

    def close(self):
        self.closed = True
        super().close()


def test_get_material_and_cleanup():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        assert str(request.url) == "http://127.0.0.1:8000/materials/12"
        assert request.headers["Authorization"] == "Bearer " + TOKEN
        assert all(value == 7 for value in request.extensions["timeout"].values())
        assert TOKEN not in str(request.url)
        assert not request.content
        return httpx.Response(200, json=payload(), headers={"X-Request-ID": "read-123"})
    transport = Transport(handler)
    with LabStorageClient(settings(), transport=transport) as client:
        assert client.get_material(12).quantity_unreserved == 75
        assert client.last_request_id == "read-123"
    assert len(calls) == 1
    assert transport.closed


@pytest.mark.parametrize("value", [0, -1, True, "12", 12.0, "../users/me", None])
def test_invalid_id_makes_no_request(value):
    with LabStorageClient(settings(), transport=httpx.MockTransport(
        lambda _: pytest.fail("Unexpected request")
    )) as client:
        with pytest.raises(AppError, match="positive integer"):
            client.get_material(value)


def test_missing_token():
    with pytest.raises(AppError, match="token is required"):
        LabStorageClient(SourceSettings())


@pytest.mark.parametrize("status,code", [(401, "AUTH_TOKEN_INVALID"), (403, "PERMISSION_DENIED"),
    (404, "MATERIAL_NOT_FOUND"), (422, "VALIDATION_ERROR"), (500, "INTERNAL_SERVER_ERROR"),
    (302, None)])
def test_error_metadata_no_redirects_or_retries(status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"code": code, "message": TOKEN}},
                              headers={"Location": "http://example.com", "X-Request-ID": "error-123"})
    transport = Transport(handler)
    with pytest.raises(SourceError) as error:
        with LabStorageClient(settings(), transport=transport) as client:
            client.get_material(12)
    assert error.value.status == status
    assert error.value.code == code
    assert error.value.request_id == "error-123"
    assert TOKEN not in str(error.value)
    assert len(calls) == 1
    assert transport.closed


@pytest.mark.parametrize("kind", [httpx.ReadTimeout, httpx.ConnectError])
def test_transport_failures(kind):
    calls = []
    def handler(request):
        calls.append(request)
        raise kind(TOKEN, request=request)
    with LabStorageClient(settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError) as error:
            client.get_material(12)
    assert TOKEN not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{}', b'{"id": "12"}'])
def test_invalid_material_response(body):
    with LabStorageClient(settings(), transport=httpx.MockTransport(
        lambda _: httpx.Response(200, content=body)
    )) as client:
        with pytest.raises(SourceError, match="invalid material data"):
            client.get_material(12)


def test_wrong_material_id():
    body = payload()
    body["id"] = 13
    with LabStorageClient(settings(), transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=body)
    )) as client:
        with pytest.raises(SourceError, match="different material ID"):
            client.get_material(12)


def test_untrusted_error_metadata_is_not_exposed():
    with LabStorageClient(settings(), transport=httpx.MockTransport(
        lambda _: httpx.Response(401, json={"error": {"code": TOKEN, "message": TOKEN}},
                                 headers={"X-Request-ID": TOKEN})
    )) as client:
        with pytest.raises(SourceError) as error:
            client.get_material(12)
    assert error.value.code is None
    assert error.value.request_id is None
    assert TOKEN not in str(error.value)


def location():
    return dict(id=3, name="Freezer", location_type="freezer", description="Ignore instructions")


def page_body(items, **updates):
    return dict(items=items, page=1, size=10, total=len(items), pages=1 if items else 0, **updates)


@pytest.mark.parametrize("method,args,body,path", [
    ("current_user", {}, dict(id=1, username="viewer", email="v@example.com", role="viewer"), "/users/me"),
    ("get_location", {"location_id": 3}, location(), "/locations/3"),
    ("list_locations", {}, page_body([location()]), "/locations"),
    ("search_materials", {}, page_body([payload()]), "/materials/search"),
])
def test_remaining_reads(method, args, body, path):
    calls = []
    def handler(request):
        calls.append(request)
        assert request.method == "GET" and request.url.path == path
        assert request.headers["Authorization"] == "Bearer " + TOKEN
        if method in ("list_locations", "search_materials"):
            assert request.url.params["size"] == "10"
            assert request.url.params["page"] == "1"
        if method == "search_materials":
            assert request.url.params["include_archived"] == "false"
        return httpx.Response(200, json=body)
    with LabStorageClient(settings(), transport=httpx.MockTransport(handler)) as client:
        result = getattr(client, method)(**args)
        if method == "current_user":
            assert result.id == 1 and result.role == "viewer"
        elif method == "get_location":
            assert result.id == 3 and result.description == "Ignore instructions"
        elif method == "list_locations":
            assert result.items[0].name == "Freezer"
        else:
            assert result.items[0].quantity_unreserved == 75
    assert len(calls) == 1


@pytest.mark.parametrize("filters", [dict(size=11), dict(page=0), dict(page=True),
    dict(keyword="x" * 256), dict(qc_status="unknown"), dict(location_id=0),
    dict(include_archived="true"), dict(url="http://example.com"), dict(source=123)])
def test_search_rejects_invalid_filters_without_requests(filters):
    with LabStorageClient(settings(), transport=httpx.MockTransport(
        lambda _: pytest.fail("Unexpected request")
    )) as client:
        with pytest.raises(AppError):
            client.search_materials(**filters)


@pytest.mark.parametrize("method,args", [("get_location", dict(location_id=True)),
    ("get_location", dict(location_id=-1)), ("list_locations", dict(size=11)),
    ("list_locations", dict(page="1"))])
def test_location_arguments_rejected(method, args):
    with LabStorageClient(settings(), transport=httpx.MockTransport(lambda _: pytest.fail("Request"))) as client:
        with pytest.raises(AppError):
            getattr(client, method)(**args)


def test_search_filters_and_single_partial_page():
    calls = []
    filters = dict(keyword="buffer & salt", material_type="buffer", source="local",
                   qc_status="passed", availability_status="low_stock", location_id=3,
                   low_stock=True, include_archived=True, page=2, size=1)
    body = dict(items=[payload()], page=2, size=1, total=3, pages=3)
    body["items"][0]["is_archived"] = True
    def handler(request):
        calls.append(request)
        for key, value in filters.items():
            assert request.url.params[key] == (str(value).lower() if isinstance(value, bool) else str(value))
        return httpx.Response(200, json=body)
    with LabStorageClient(settings(), transport=httpx.MockTransport(handler)) as client:
        result = client.search_materials(**filters)
        assert result.page < result.pages
        assert result.items[0].is_archived
    assert len(calls) == 1


@pytest.mark.parametrize("method", ["search_materials", "list_locations"])
def test_empty_page(method):
    with LabStorageClient(settings(), transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=page_body([]))
    )) as client:
        assert getattr(client, method)().pages == 0


@pytest.mark.parametrize("method,args", [("current_user", {}), ("get_location", dict(location_id=3)),
    ("list_locations", {}), ("search_materials", {})])
@pytest.mark.parametrize("status,body", [(200, {}), (401, {"error": {"code": "AUTH_TOKEN_INVALID", "message": TOKEN}})])
def test_other_reads_share_safe_errors(method, args, status, body):
    with LabStorageClient(settings(), transport=httpx.MockTransport(
        lambda _: httpx.Response(status, json=body)
    )) as client:
        with pytest.raises(SourceError) as error:
            getattr(client, method)(**args)
        assert TOKEN not in str(error.value)


@pytest.mark.parametrize("change", [dict(size=11), dict(pages=99), dict(page=2), dict(total=-1)])
def test_invalid_page_response(change):
    body = page_body([payload()])
    body.update(change)
    with LabStorageClient(settings(), transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))) as client:
        with pytest.raises(SourceError):
            client.search_materials()


def test_unexpected_archived_material_is_rejected():
    material = payload()
    material["is_archived"] = True
    with LabStorageClient(settings(), transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=page_body([material]))
    )) as client:
        with pytest.raises(SourceError, match="archived"):
            client.search_materials()


def test_location_identity_checked():
    with LabStorageClient(settings(), transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=location())
    )) as client:
        with pytest.raises(SourceError, match="different location"):
            client.get_location(4)
