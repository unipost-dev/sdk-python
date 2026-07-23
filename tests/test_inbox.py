from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import inspect
from socketserver import TCPServer
from threading import Thread
from typing import Optional
from urllib.parse import parse_qs, urlsplit
from urllib.error import HTTPError
from urllib.request import Request

import pytest
import httpx

from unipost import AsyncUniPost, InboxItem, InboxListResponse, UniPost
from unipost.errors import RateLimitError, UniPostError
from unipost.http import HttpClient
from unipost.resources.inbox import Inbox
import unipost.http as http_module
import unipost.resources.inbox as inbox_resource
import unipost.types as types


@pytest.mark.asyncio
async def test_async_client_exposes_inbox_resource():
    client = AsyncUniPost(api_key="up_test_inbox")

    assert client.inbox is not None


class FakeHTTP:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, object]] = []

    def get(self, path: str, query=None):
        self.requests.append(("GET", path, query))
        return {
            "data": [
                {
                    "id": "inbox_1",
                    "social_account_id": "sa_1",
                    "workspace_id": "ws_1",
                    "source": "ig_comment",
                    "external_id": "comment_1",
                    "thread_key": "thread_1",
                    "thread_status": "open",
                    "is_read": False,
                    "is_own": False,
                    "received_at": "2026-07-22T12:00:00Z",
                    "created_at": "2026-07-22T12:00:01Z",
                    "parent_external_id": "comment_parent_1",
                    "assigned_to": "user_2",
                    "linked_post_id": "post_1",
                    "author_name": "Ada",
                    "author_id": "author_1",
                    "author_avatar_url": "https://example.test/author.png",
                    "body": "Hello",
                    "account_name": "UniPost",
                    "account_platform": "instagram",
                    "account_avatar_url": "https://example.test/account.png",
                    "x_credits_counted": 2,
                    "x_credit_operation": "reply_read",
                    "x_credit_catalog_version": "2026-07",
                    "x_credit_billing_mode": "metered",
                    "url": "https://instagram.example/comment_1",
                    "unknown_item_field": "ignored",
                }
            ],
            "request_id": "req_1",
            "next_cursor": "must_be_ignored",
        }


def _client(monkeypatch: pytest.MonkeyPatch, http: FakeHTTP) -> UniPost:
    monkeypatch.setattr("unipost.client.HttpClient", lambda **_kwargs: http)
    return UniPost(api_key="up_test_inbox")


def test_managed_user_list_injects_scope_and_all_filters(monkeypatch: pytest.MonkeyPatch):
    http = FakeHTTP()
    client = _client(monkeypatch, http)

    result = client.inbox.managed_user("user A").list(
        source="ig_comment",
        is_read=False,
        is_own=False,
        limit=25,
    )

    assert http.requests == [
        (
            "GET",
            "/v1/inbox",
            {
                "inbox_scope": "managed_user",
                "external_user_id": "user A",
                "source": "ig_comment",
                "is_read": "false",
                "is_own": "false",
                "limit": 25,
            },
        )
    ]
    assert isinstance(result, InboxListResponse)
    assert result.request_id == "req_1"
    assert result.data == [
        InboxItem(
            id="inbox_1",
            social_account_id="sa_1",
            workspace_id="ws_1",
            source="ig_comment",
            external_id="comment_1",
            thread_key="thread_1",
            thread_status="open",
            is_read=False,
            is_own=False,
            received_at="2026-07-22T12:00:00Z",
            created_at="2026-07-22T12:00:01Z",
            parent_external_id="comment_parent_1",
            assigned_to="user_2",
            linked_post_id="post_1",
            author_name="Ada",
            author_id="author_1",
            author_avatar_url="https://example.test/author.png",
            body="Hello",
            account_name="UniPost",
            account_platform="instagram",
            account_avatar_url="https://example.test/account.png",
            x_credits_counted=2,
            x_credit_operation="reply_read",
            x_credit_catalog_version="2026-07",
            x_credit_billing_mode="metered",
            url="https://instagram.example/comment_1",
        )
    ]
    assert not hasattr(result, "next_cursor")


def test_managed_user_id_is_encoded_in_real_http_url(monkeypatch: pytest.MonkeyPatch):
    requests = []

    class StubResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc_value, _traceback):
            return False

        def read(self) -> bytes:
            return json.dumps({"data": [], "request_id": "req_1"}).encode("utf-8")

    def fake_urlopen(request, *, timeout, context, follow_redirects):
        requests.append(request)
        return StubResponse()

    monkeypatch.setattr("unipost.http._open_request", fake_urlopen)
    http = HttpClient(
        api_key="up_test_inbox",
        base_url="https://api.example.test",
        timeout=5,
    )

    Inbox(http).managed_user("user A").list()

    assert len(requests) == 1
    request_url = requests[0].get_full_url()
    assert "user A" not in request_url
    assert (
        "external_user_id=user+A" in request_url
        or "external_user_id=user%20A" in request_url
    )
    assert parse_qs(urlsplit(request_url).query) == {
        "inbox_scope": ["managed_user"],
        "external_user_id": ["user A"],
    }


def test_workspace_list_sends_only_workspace_scope(monkeypatch: pytest.MonkeyPatch):
    http = FakeHTTP()
    client = _client(monkeypatch, http)

    client.inbox.workspace().list()

    assert http.requests == [
        ("GET", "/v1/inbox", {"inbox_scope": "workspace"})
    ]


@pytest.mark.parametrize("external_user_id", ["", " ", "\t\n"])
def test_managed_user_rejects_blank_ids_before_request(
    monkeypatch: pytest.MonkeyPatch,
    external_user_id: str,
):
    http = FakeHTTP()
    client = _client(monkeypatch, http)

    with pytest.raises(ValueError, match="external_user_id"):
        client.inbox.managed_user(external_user_id)

    assert http.requests == []


@pytest.mark.parametrize(
    ("scope_factory", "unexpected"),
    [
        (lambda inbox: inbox.managed_user("user_1"), {"inbox_scope": "workspace"}),
        (lambda inbox: inbox.managed_user("user_1"), {"external_user_id": "user_2"}),
        (lambda inbox: inbox.workspace(), {"cursor": "cursor_1"}),
    ],
)
def test_list_rejects_scope_and_cursor_keywords_before_request(
    monkeypatch: pytest.MonkeyPatch,
    scope_factory,
    unexpected: dict[str, str],
):
    http = FakeHTTP()
    client = _client(monkeypatch, http)
    scoped = scope_factory(client.inbox)

    with pytest.raises(TypeError):
        scoped.list(**unexpected)

    assert http.requests == []


def test_scoped_resources_do_not_expose_or_allow_scope_mutation(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _client(monkeypatch, FakeHTTP())
    scoped = client.inbox.managed_user("user_1")

    assert not hasattr(scoped, "scope")
    with pytest.raises(AttributeError):
        setattr(scoped, "_scope", "workspace")
    with pytest.raises(AttributeError):
        setattr(scoped, "_external_user_id", "user_2")


def test_inbox_resource_itself_is_immutable():
    inbox = Inbox(FakeHTTP())

    with pytest.raises(AttributeError):
        setattr(inbox, "_http", FakeHTTP())


def test_response_aware_http_retains_success_status_headers_and_body(
    monkeypatch: pytest.MonkeyPatch,
):
    class StubResponse:
        status = 202
        headers = {"X-UniPost-Operation-Id": " op_1 "}

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc_value, _traceback):
            return False

        def read(self) -> bytes:
            return json.dumps({"error": {"code": "accepted"}}).encode("utf-8")

    monkeypatch.setattr(
        "unipost.http._open_request",
        lambda *_args, **_kwargs: StubResponse(),
    )
    http = HttpClient(
        api_key="up_test_inbox",
        base_url="https://api.example.test",
        timeout=5,
    )

    response = http._request_with_response("POST", "/v1/inbox/item/reply")

    assert response.status == 202
    assert response.headers == {"x-unipost-operation-id": " op_1 "}
    assert response.body == {"error": {"code": "accepted"}}


def test_reply_decoder_accepts_only_plain_response_data():
    result = inbox_resource._decode_reply_response(
        202,
        {"x-unipost-operation-id": " op_plain "},
        {
            "error": {
                "code": "X_REMOTE_ACCEPTED_RECONCILING",
                "message": "Accepted",
            },
            "request_id": "req_plain",
        },
    )

    assert result == types.InboxReplyReconciling(
        operation_id="op_plain",
        message="Accepted",
        request_id="req_plain",
    )


@pytest.mark.parametrize(
    ("status", "headers", "body"),
    [
        (
            202,
            {"x-unipost-operation-id": "op_1"},
            {
                "error": {
                    "code": "X_REMOTE_ACCEPTED_RECONCILING",
                    "message": "Accepted",
                },
                "request_id": 123,
            },
        ),
        (200, {}, []),
        (200, {}, {"data": []}),
        (200, {}, {"data": {"social_account_id": "sa_missing_id"}}),
    ],
)
def test_reply_decoder_explicit_invalid_shapes_fail_closed(
    status: int,
    headers: dict[str, str],
    body: object,
):
    with pytest.raises(
        ValueError,
        match=rf"^Failed to decode Inbox reply response with status {status}\.$",
    ):
        inbox_resource._decode_reply_response(status, headers, body)


def test_shared_inbox_scope_and_list_helpers_preserve_contract():
    with pytest.raises(ValueError, match="external_user_id"):
        inbox_resource._validate_managed_user_id(" \t")

    scope_query = inbox_resource._build_scope_query("managed_user", "user A")
    list_query = inbox_resource._build_list_query(
        scope_query,
        source="ig_comment",
        is_read=False,
        is_own=False,
        limit=25,
    )
    response = inbox_resource._decode_list_response(
        {
            "data": [{**_reply_item_payload(), "unknown_item_field": "ignored"}],
            "request_id": "req_shared",
            "next_cursor": "must_be_ignored",
        }
    )

    assert scope_query == {
        "inbox_scope": "managed_user",
        "external_user_id": "user A",
    }
    assert list_query == {
        **scope_query,
        "source": "ig_comment",
        "is_read": "false",
        "is_own": "false",
        "limit": 25,
    }
    assert response == InboxListResponse(
        data=[InboxItem(**_reply_item_payload())],
        request_id="req_shared",
    )
    assert not hasattr(response, "next_cursor")


@pytest.mark.parametrize(
    ("scope", "external_user_id"),
    [
        ("workspace", "user_1"),
        ("managed_user", None),
        ("managed_user", " \t"),
        ("invalid_scope", None),
    ],
)
def test_shared_scope_query_rejects_invalid_scope_id_correlations(
    scope: str,
    external_user_id: Optional[str],
):
    with pytest.raises(ValueError):
        inbox_resource._build_scope_query(scope, external_user_id)


def test_shared_scope_query_accepts_only_valid_scope_id_correlations():
    assert inbox_resource._build_scope_query("workspace", None) == {
        "inbox_scope": "workspace"
    }
    assert inbox_resource._build_scope_query("managed_user", "user_1") == {
        "inbox_scope": "managed_user",
        "external_user_id": "user_1",
    }


def _reply_item_payload() -> dict[str, object]:
    return {
        "id": "inbox_1",
        "social_account_id": "sa_1",
        "workspace_id": "ws_1",
        "source": "ig_comment",
        "external_id": "comment_1",
        "thread_key": "thread_1",
        "thread_status": "open",
        "is_read": False,
        "is_own": True,
        "received_at": "2026-07-22T12:00:00Z",
        "created_at": "2026-07-22T12:00:01Z",
        "body": "Thanks",
    }


class _StubResponse:
    def __init__(
        self,
        status: int,
        body: object = None,
        *,
        headers: Optional[dict[str, str]] = None,
        raw_body: Optional[bytes] = None,
    ) -> None:
        self.status = status
        self.headers = headers or {}
        self._body = (
            raw_body
            if raw_body is not None
            else (json.dumps(body).encode("utf-8") if body is not None else b"")
        )

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        return False

    def read(self) -> bytes:
        return self._body


class _LoopbackHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


def _http_error(
    status: int,
    code: str,
    *,
    normalized_code: str = "NORMALIZED",
    retry_after: object = 0,
    retry_after_header: str = "0",
):
    body = {
        "error": {
            "code": code,
            "normalized_code": normalized_code,
            "message": "Reply failed",
            "retry_after": retry_after,
        }
    }
    return HTTPError(
        "https://api.example.test/v1/inbox/item/reply",
        status,
        "Reply failed",
        {"Retry-After": retry_after_header},
        BytesIO(json.dumps(body).encode("utf-8")),
    )


def _stub_urlopen(
    monkeypatch: pytest.MonkeyPatch,
    outcomes: list[object],
):
    requests = []
    calls = []

    def fake_urlopen(request, *, timeout, context, follow_redirects):
        requests.append(request)
        calls.append((timeout, context, follow_redirects))
        outcome = outcomes[len(requests) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr("unipost.http._open_request", fake_urlopen)
    return requests, calls


def _real_client() -> UniPost:
    return UniPost(
        api_key="up_test_inbox_secret",
        base_url="https://api.example.test",
        timeout=5,
    )


def test_reply_200_returns_completed_and_sends_exact_request(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, calls = _stub_urlopen(
        monkeypatch,
        [
            _StubResponse(
                200,
                {"data": _reply_item_payload(), "request_id": "ignored"},
                headers={"X-UniPost-Operation-Id": " op_completed "},
            )
        ],
    )
    client = _real_client()

    result = client.inbox.managed_user("user A").reply(
        "item /?#",
        text="Thanks",
        idempotency_key="idem-exact-value",
    )

    assert len(requests) == 1
    assert len(calls) == 1
    assert calls[0][0] == 5
    request = requests[0]
    assert request.get_method() == "POST"
    url = urlsplit(request.get_full_url())
    assert url.path == "/v1/inbox/item%20%2F%3F%23/reply"
    assert parse_qs(url.query) == {
        "inbox_scope": ["managed_user"],
        "external_user_id": ["user A"],
    }
    assert json.loads(request.data.decode("utf-8")) == {"text": "Thanks"}
    request_headers = {key.lower(): value for key, value in request.header_items()}
    assert request_headers["idempotency-key"] == "idem-exact-value"

    assert isinstance(result, types.InboxReplyCompleted)
    assert result.state == "completed"
    assert result.operation_id == "op_completed"
    assert result.item == InboxItem(**_reply_item_payload())


def test_reply_200_omits_blank_operation_and_absent_idempotency_headers(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [
            _StubResponse(
                200,
                {"data": _reply_item_payload()},
                headers={"x-unipost-operation-id": "  "},
            )
        ],
    )

    result = _real_client().inbox.workspace().reply("item_1", text="Thanks")

    assert len(requests) == 1
    request_headers = {key.lower(): value for key, value in requests[0].header_items()}
    assert "idempotency-key" not in request_headers
    assert result.operation_id is None


def test_reply_202_returns_reconciling_without_item(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [
            _StubResponse(
                202,
                {
                    "error": {
                        "code": "X_REMOTE_ACCEPTED_RECONCILING",
                        "message": "Accepted remotely; reconciling",
                    },
                    "request_id": "req_202",
                },
                headers={"x-UNIPOST-operation-ID": " op_reconcile "},
            )
        ],
    )

    result = _real_client().inbox.workspace().reply("item_1", text="Thanks")

    assert len(requests) == 1
    assert isinstance(result, types.InboxReplyReconciling)
    assert result.state == "reconciling"
    assert result.operation_id == "op_reconcile"
    assert result.code == "X_REMOTE_ACCEPTED_RECONCILING"
    assert result.message == "Accepted remotely; reconciling"
    assert result.request_id == "req_202"
    assert not hasattr(result, "item")


def test_reply_does_not_follow_cross_origin_redirects():
    source_requests = []
    target_requests = []

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            target_requests.append(dict(self.headers.items()))
            body = json.dumps({"data": _reply_item_payload()}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    target_server = _LoopbackHTTPServer(("127.0.0.1", 0), TargetHandler)
    target_thread = Thread(target=target_server.serve_forever, daemon=True)
    target_thread.start()
    target_url = f"http://127.0.0.1:{target_server.server_port}/capture"

    class SourceHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            source_requests.append(dict(self.headers.items()))
            content_length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(content_length)
            body = json.dumps(
                {"error": {"code": "REDIRECT", "message": "Redirect denied"}}
            ).encode("utf-8")
            self.send_response(302)
            self.send_header("Location", target_url)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    source_server = _LoopbackHTTPServer(("127.0.0.1", 0), SourceHandler)
    source_thread = Thread(target=source_server.serve_forever, daemon=True)
    source_thread.start()

    try:
        client = UniPost(
            api_key="up_test_redirect_key",
            base_url=f"http://127.0.0.1:{source_server.server_port}",
            timeout=5,
        )
        with pytest.raises(UniPostError) as raised:
            client.inbox.workspace().reply(
                "item_1",
                text="Thanks",
                idempotency_key="idem-redirect-test",
            )

        assert raised.value.status == 302
        assert len(source_requests) == 1
        assert target_requests == []
        assert all("Authorization" not in headers for headers in target_requests)
        assert all("Idempotency-Key" not in headers for headers in target_requests)
    finally:
        source_server.shutdown()
        source_server.server_close()
        source_thread.join(timeout=5)
        target_server.shutdown()
        target_server.server_close()
        target_thread.join(timeout=5)


def test_ordinary_request_strips_secrets_on_cross_origin_redirect():
    source_requests = []
    target_requests = []

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            target_requests.append(dict(self.headers.items()))
            body = json.dumps({"data": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    target_server = _LoopbackHTTPServer(("127.0.0.1", 0), TargetHandler)
    target_thread = Thread(target=target_server.serve_forever, daemon=True)
    target_thread.start()
    target_url = f"http://127.0.0.1:{target_server.server_port}/capture"

    class SourceHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            source_requests.append(dict(self.headers.items()))
            content_length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(content_length)
            self.send_response(302)
            self.send_header("Location", target_url)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, _format, *_args):
            return

    source_server = _LoopbackHTTPServer(("127.0.0.1", 0), SourceHandler)
    source_thread = Thread(target=source_server.serve_forever, daemon=True)
    source_thread.start()

    try:
        http = HttpClient(
            api_key="up_test_redirect_key",
            base_url=f"http://127.0.0.1:{source_server.server_port}",
            timeout=5,
        )

        result = http.request(
            "POST",
            "/ordinary",
            body={"text": "Thanks"},
            headers={"Idempotency-Key": "idem-redirect-test"},
        )

        assert result == {"data": "ok"}
        assert len(source_requests) == 1
        source_headers = {
            key.lower(): value for key, value in source_requests[0].items()
        }
        assert source_headers["authorization"] == "Bearer up_test_redirect_key"
        assert source_headers["idempotency-key"] == "idem-redirect-test"
        assert len(target_requests) == 1
        target_headers = {
            key.lower(): value for key, value in target_requests[0].items()
        }
        assert "authorization" not in target_headers
        assert "idempotency-key" not in target_headers
    finally:
        source_server.shutdown()
        source_server.server_close()
        source_thread.join(timeout=5)
        target_server.shutdown()
        target_server.server_close()
        target_thread.join(timeout=5)


def test_safe_redirect_retains_headers_for_normalized_same_origin():
    request = Request(
        "HTTP://user@example.test:80/start",
        data=b"{}",
        headers={
            "Authorization": "Bearer up_test_redirect_key",
            "Idempotency-Key": "idem-redirect-test",
            "X-Test": "preserved",
        },
        method="POST",
    )

    redirected = http_module._SafeRedirectHandler().redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "http://EXAMPLE.TEST/next",
    )

    redirected_headers = {
        key.lower(): value for key, value in redirected.header_items()
    }
    assert redirected_headers["authorization"] == "Bearer up_test_redirect_key"
    assert redirected_headers["idempotency-key"] == "idem-redirect-test"
    assert redirected_headers["x-test"] == "preserved"
    assert http_module._url_origin("https://example.test/path") == (
        "https",
        "example.test",
        443,
    )
    assert http_module._url_origin("http://trusted.test@evil.test/path") == (
        "http",
        "evil.test",
        80,
    )


@pytest.mark.parametrize("item_id", ["", ".", ".."])
def test_reply_rejects_invalid_item_ids_before_request(
    monkeypatch: pytest.MonkeyPatch,
    item_id: str,
):
    requests, _calls = _stub_urlopen(monkeypatch, [])

    with pytest.raises(ValueError, match="item_id"):
        _real_client().inbox.workspace().reply(item_id, text="Thanks")

    assert requests == []


def test_reply_text_is_required_keyword_only(monkeypatch: pytest.MonkeyPatch):
    requests, _calls = _stub_urlopen(monkeypatch, [])
    scoped = _real_client().inbox.workspace()

    with pytest.raises(TypeError):
        scoped.reply("item_1", "Thanks")
    with pytest.raises(TypeError):
        scoped.reply("item_1")

    assert requests == []


@pytest.mark.parametrize(
    "idempotency_key",
    [
        "up_test_idem_secret\r\nX-Evil: injected",
        "up_test_idem_secret\x00",
        "up_test_idem_secret\x7f",
        "up_test_idem_secret\x85",
        "up_test_idem_secret🔐",
    ],
)
def test_reply_rejects_unsafe_idempotency_keys_before_request(
    monkeypatch: pytest.MonkeyPatch,
    idempotency_key: str,
):
    requests, _calls = _stub_urlopen(monkeypatch, [])

    with pytest.raises(ValueError) as raised:
        _real_client().inbox.workspace().reply(
            "item_1",
            text="Thanks",
            idempotency_key=idempotency_key,
        )

    assert requests == []
    assert str(raised.value) == "Invalid idempotency_key."
    assert "up_test_idem_secret" not in str(raised.value)
    assert "up_test_idem_secret" not in repr(raised.value)


@pytest.mark.parametrize(
    ("case", "status", "body", "headers"),
    [
        ("202 missing operation header", 202, {
            "error": {
                "code": "X_REMOTE_ACCEPTED_RECONCILING",
                "message": "Accepted",
            }
        }, {}),
        ("202 blank operation header", 202, {
            "error": {
                "code": "X_REMOTE_ACCEPTED_RECONCILING",
                "message": "Accepted",
            }
        }, {"X-UniPost-Operation-Id": "  "}),
        ("202 wrong code", 202, {
            "error": {"code": "WRONG_CODE", "message": "Accepted"}
        }, {"X-UniPost-Operation-Id": "op_1"}),
        ("202 missing code", 202, {
            "error": {"message": "Accepted"}
        }, {"X-UniPost-Operation-Id": "op_1"}),
        ("202 missing error object", 202, {}, {
            "X-UniPost-Operation-Id": "op_1"
        }),
        ("202 missing message", 202, {
            "error": {"code": "X_REMOTE_ACCEPTED_RECONCILING"}
        }, {"X-UniPost-Operation-Id": "op_1"}),
        ("202 unexpected data envelope", 202, {
            "data": _reply_item_payload(),
            "error": {
                "code": "X_REMOTE_ACCEPTED_RECONCILING",
                "message": "Accepted",
            },
        }, {"X-UniPost-Operation-Id": "op_1"}),
        ("200 missing data", 200, {}, {}),
        ("201 with data", 201, {"data": _reply_item_payload()}, {}),
        ("204 empty", 204, None, {}),
    ],
    ids=lambda value: value if isinstance(value, str) and value[0].isdigit() else None,
)
def test_reply_malformed_success_fails_closed_after_one_request(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    status: int,
    body: object,
    headers: dict[str, str],
):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [_StubResponse(status, body, headers=headers)],
    )

    with pytest.raises(
        ValueError,
        match=rf"^Failed to decode Inbox reply response with status {status}\.$",
    ):
        _real_client().inbox.workspace().reply("item_1", text="Thanks")

    assert requests, case
    assert len(requests) == 1


def test_reply_malformed_success_json_fails_closed_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [
            _StubResponse(
                202,
                headers={"X-UniPost-Operation-Id": "op_1"},
                raw_body=b'{"api_key":"up_test_inbox_secret"',
            )
        ],
    )

    with pytest.raises(ValueError) as raised:
        _real_client().inbox.workspace().reply(
            "item_1",
            text="Thanks",
            idempotency_key="idem-secret-value",
        )

    assert len(requests) == 1
    assert str(raised.value) == "Failed to decode Inbox reply response."
    representation = repr(raised.value)
    assert "up_test_inbox_secret" not in representation
    assert "idem-secret-value" not in representation


def test_reply_invalid_utf8_fails_closed_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
):
    sensitive_marker = b"up_test_inbox_secret_adjacent"
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [
            _StubResponse(
                202,
                headers={"X-UniPost-Operation-Id": "op_1"},
                raw_body=sensitive_marker + b"\xff",
            )
        ],
    )

    with pytest.raises(ValueError) as raised:
        _real_client().inbox.workspace().reply(
            "item_1",
            text="Thanks",
            idempotency_key="idem-secret-value",
        )

    assert len(requests) == 1
    assert str(raised.value) == "Failed to decode Inbox reply response."
    representation = repr(raised.value)
    assert "up_test_inbox_secret" not in representation
    assert "idem-secret-value" not in representation
    assert "up_test_inbox_secret_adjacent" not in representation


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, "VALIDATION_ERROR"),
        (402, "X_MONTHLY_USAGE_LIMIT_EXCEEDED"),
        (409, "X_RECONNECT_REQUIRED"),
        (409, "NEEDS_RECONNECT"),
        (409, "IDEMPOTENCY_KEY_CONFLICT"),
        (409, "X_WRITE_OUTCOME_PENDING"),
        (409, "X_WRITE_NEEDS_RECONCILIATION"),
        (409, "X_USAGE_REVERSAL_PENDING"),
        (422, "VALIDATION_ERROR"),
        (422, "PLATFORM_ERROR"),
    ],
)
def test_reply_non_2xx_preserves_raw_server_code_after_one_request(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    code: str,
):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [_http_error(status, code, normalized_code="NORMALIZED_DIFFERENT")],
    )

    with pytest.raises(UniPostError) as raised:
        _real_client().inbox.workspace().reply("item_1", text="Thanks")

    assert len(requests) == 1
    assert raised.value.status == status
    assert raised.value.code == code


def test_ordinary_request_keeps_normalized_code_precedence(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [_http_error(409, "RAW_CODE", normalized_code="NORMALIZED_CODE")],
    )

    with pytest.raises(UniPostError) as raised:
        _real_client().inbox._http.request("POST", "/ordinary")

    assert len(requests) == 1
    assert raised.value.code == "NORMALIZED_CODE"


def test_reply_429_is_not_slept_or_replayed(monkeypatch: pytest.MonkeyPatch):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [_http_error(429, "RATE_LIMITED")],
    )
    sleeps = []
    monkeypatch.setattr("unipost.http.time.sleep", sleeps.append)

    with pytest.raises(RateLimitError):
        _real_client().inbox.workspace().reply("item_1", text="Thanks")

    assert len(requests) == 1
    assert sleeps == []


@pytest.mark.parametrize(
    ("retry_after", "expected_retry_after"),
    [
        ("up_test_retry_secret", 1),
        (["up_test_retry_secret"], 1),
        ({"marker": "up_test_retry_secret"}, 1),
        (10**9, 60),
        (float("inf"), 1),
        ("NaN", 1),
        (True, 1),
    ],
)
def test_reply_429_sanitizes_malformed_retry_after_body(
    monkeypatch: pytest.MonkeyPatch,
    retry_after: object,
    expected_retry_after: int,
):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [_http_error(429, "RATE_LIMITED", retry_after=retry_after)],
    )
    sleeps = []
    monkeypatch.setattr("unipost.http.time.sleep", sleeps.append)

    with pytest.raises(RateLimitError) as raised:
        _real_client().inbox.workspace().reply("item_1", text="Thanks")

    assert len(requests) == 1
    assert sleeps == []
    assert raised.value.status == 429
    assert raised.value.retry_after == expected_retry_after
    assert "up_test_retry_secret" not in str(raised.value)
    assert "up_test_retry_secret" not in repr(raised.value)


@pytest.mark.parametrize(
    ("retry_after_header", "expected_sleep"),
    [
        ("up_test_retry_header_secret", 1),
        ("1000000000", 60),
        ("Infinity", 1),
    ],
)
def test_ordinary_request_sanitizes_retry_after_header_and_completes_retry(
    monkeypatch: pytest.MonkeyPatch,
    retry_after_header: str,
    expected_sleep: int,
):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [
            _http_error(
                429,
                "RATE_LIMITED",
                retry_after_header=retry_after_header,
            ),
            _StubResponse(200, {"data": "ok"}),
        ],
    )
    sleeps = []
    monkeypatch.setattr("unipost.http.time.sleep", sleeps.append)

    result = _real_client().inbox._http.request("GET", "/ordinary")

    assert result == {"data": "ok"}
    assert len(requests) == 2
    assert sleeps == [expected_sleep]


def test_ordinary_request_still_retries_429(monkeypatch: pytest.MonkeyPatch):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [
            _http_error(429, "RATE_LIMITED"),
            _StubResponse(200, {"data": "ok"}),
        ],
    )
    sleeps = []
    monkeypatch.setattr("unipost.http.time.sleep", sleeps.append)

    result = _real_client().inbox._http.request("GET", "/ordinary")

    assert result == {"data": "ok"}
    assert len(requests) == 2
    assert sleeps == [0]


def _install_async_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler,
):
    requests: list[httpx.Request] = []
    client_options: list[dict[str, object]] = []
    real_async_client = httpx.AsyncClient

    async def dispatch(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(dispatch)

    def async_client_factory(*args, **kwargs):
        client_options.append(dict(kwargs))
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", async_client_factory)
    return requests, client_options


def _async_client() -> AsyncUniPost:
    return AsyncUniPost(
        api_key="up_test_inbox_secret",
        base_url="https://api.example.test",
        timeout=5,
    )


@pytest.mark.asyncio
async def test_async_managed_user_list_matches_sync_contract(
    monkeypatch: pytest.MonkeyPatch,
):
    payload = {**_reply_item_payload(), "unknown_item_field": "ignored"}
    requests, client_options = _install_async_transport(
        monkeypatch,
        lambda _request: httpx.Response(
            200,
            json={
                "data": [payload],
                "request_id": "req_async_list",
                "next_cursor": "must_be_ignored",
            },
        ),
    )

    scoped = _async_client().inbox.managed_user("user A")
    result = await scoped.list(
        source="ig_comment",
        is_read=False,
        is_own=False,
        limit=25,
    )

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "GET"
    assert request.url.path == "/v1/inbox"
    assert "user A" not in str(request.url)
    assert parse_qs(request.url.query.decode("ascii")) == {
        "inbox_scope": ["managed_user"],
        "external_user_id": ["user A"],
        "source": ["ig_comment"],
        "is_read": ["false"],
        "is_own": ["false"],
        "limit": ["25"],
    }
    assert client_options == [{"timeout": 5, "follow_redirects": False}]
    assert result == InboxListResponse(
        data=[InboxItem(**_reply_item_payload())],
        request_id="req_async_list",
    )
    assert not hasattr(result, "next_cursor")


@pytest.mark.asyncio
async def test_async_workspace_list_sends_only_workspace_scope(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: httpx.Response(
            200,
            json={"data": [], "request_id": "req_workspace"},
        ),
    )

    result = await _async_client().inbox.workspace().list()

    assert len(requests) == 1
    assert parse_qs(requests[0].url.query.decode("ascii")) == {
        "inbox_scope": ["workspace"]
    }
    assert result == InboxListResponse(data=[], request_id="req_workspace")


@pytest.mark.asyncio
@pytest.mark.parametrize("external_user_id", ["", " ", "\t\n"])
async def test_async_managed_user_rejects_blank_ids_before_request(
    monkeypatch: pytest.MonkeyPatch,
    external_user_id: str,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: pytest.fail("network request was not expected"),
    )

    with pytest.raises(ValueError, match="external_user_id"):
        _async_client().inbox.managed_user(external_user_id)

    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scope_factory", "unexpected"),
    [
        (lambda inbox: inbox.managed_user("user_1"), {"inbox_scope": "workspace"}),
        (lambda inbox: inbox.managed_user("user_1"), {"external_user_id": "user_2"}),
        (lambda inbox: inbox.workspace(), {"cursor": "cursor_1"}),
    ],
)
async def test_async_list_rejects_scope_and_cursor_keywords_before_request(
    monkeypatch: pytest.MonkeyPatch,
    scope_factory,
    unexpected: dict[str, str],
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: pytest.fail("network request was not expected"),
    )
    scoped = scope_factory(_async_client().inbox)

    with pytest.raises(TypeError):
        await scoped.list(**unexpected)

    assert requests == []


@pytest.mark.asyncio
async def test_async_scoped_resources_are_immutable_and_match_sync_signatures():
    inbox = _async_client().inbox
    scoped = inbox.managed_user("user_1")
    sync_scoped = Inbox(FakeHTTP()).managed_user("user_1")

    assert not hasattr(scoped, "scope")
    with pytest.raises(AttributeError):
        setattr(scoped, "_scope", "workspace")
    with pytest.raises(AttributeError):
        setattr(scoped, "_external_user_id", "user_2")
    assert inspect.signature(scoped.list) == inspect.signature(sync_scoped.list)


@pytest.mark.asyncio
async def test_async_reply_200_matches_exact_sync_request_and_result(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, client_options = _install_async_transport(
        monkeypatch,
        lambda _request: httpx.Response(
            200,
            headers={"X-UniPost-Operation-Id": " op_completed "},
            json={"data": _reply_item_payload(), "request_id": "ignored"},
        ),
    )
    scoped = _async_client().inbox.managed_user("user A")

    result = await scoped.reply(
        "item /?#",
        text="Thanks",
        idempotency_key="idem-exact-value",
    )

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/inbox/item /?#/reply"
    assert request.url.raw_path.split(b"?")[0] == b"/v1/inbox/item%20%2F%3F%23/reply"
    assert parse_qs(request.url.query.decode("ascii")) == {
        "inbox_scope": ["managed_user"],
        "external_user_id": ["user A"],
    }
    assert json.loads(request.content.decode("utf-8")) == {"text": "Thanks"}
    assert request.headers["idempotency-key"] == "idem-exact-value"
    assert client_options == [{"timeout": 5, "follow_redirects": False}]
    assert result == types.InboxReplyCompleted(
        item=InboxItem(**_reply_item_payload()),
        operation_id="op_completed",
    )


@pytest.mark.asyncio
async def test_async_reply_200_omits_optional_headers_and_operation(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: httpx.Response(
            200,
            headers={"X-UniPost-Operation-Id": "  "},
            json={"data": _reply_item_payload()},
        ),
    )

    result = await _async_client().inbox.workspace().reply("item_1", text="Thanks")

    assert len(requests) == 1
    assert "idempotency-key" not in requests[0].headers
    assert result.operation_id is None


@pytest.mark.asyncio
async def test_async_reply_202_returns_exact_reconciling_result(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: httpx.Response(
            202,
            headers={"x-UNIPOST-operation-ID": " op_reconcile "},
            json={
                "error": {
                    "code": "X_REMOTE_ACCEPTED_RECONCILING",
                    "message": "Accepted remotely; reconciling",
                },
                "request_id": "req_202",
            },
        ),
    )

    result = await _async_client().inbox.workspace().reply("item_1", text="Thanks")

    assert len(requests) == 1
    assert result == types.InboxReplyReconciling(
        operation_id="op_reconcile",
        message="Accepted remotely; reconciling",
        request_id="req_202",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("item_id", ["", ".", ".."])
async def test_async_reply_rejects_invalid_item_ids_before_request(
    monkeypatch: pytest.MonkeyPatch,
    item_id: str,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: pytest.fail("network request was not expected"),
    )

    with pytest.raises(ValueError, match="item_id"):
        await _async_client().inbox.workspace().reply(item_id, text="Thanks")

    assert requests == []


@pytest.mark.asyncio
async def test_async_reply_text_is_required_keyword_only(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: pytest.fail("network request was not expected"),
    )
    scoped = _async_client().inbox.workspace()

    with pytest.raises(TypeError):
        await scoped.reply("item_1", "Thanks")
    with pytest.raises(TypeError):
        await scoped.reply("item_1")

    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "idempotency_key",
    [
        "up_test_idem_secret\r\nX-Evil: injected",
        "up_test_idem_secret\x00",
        "up_test_idem_secret\x7f",
        "up_test_idem_secret\x85",
        "up_test_idem_secret🔐",
    ],
)
async def test_async_reply_rejects_unsafe_idempotency_keys_before_request(
    monkeypatch: pytest.MonkeyPatch,
    idempotency_key: str,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: pytest.fail("network request was not expected"),
    )

    with pytest.raises(ValueError) as raised:
        await _async_client().inbox.workspace().reply(
            "item_1",
            text="Thanks",
            idempotency_key=idempotency_key,
        )

    assert requests == []
    assert str(raised.value) == "Invalid idempotency_key."
    assert "up_test_idem_secret" not in repr(raised.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "status", "body", "headers"),
    [
        ("202 missing operation header", 202, {
            "error": {
                "code": "X_REMOTE_ACCEPTED_RECONCILING",
                "message": "Accepted",
            }
        }, {}),
        ("202 blank operation header", 202, {
            "error": {
                "code": "X_REMOTE_ACCEPTED_RECONCILING",
                "message": "Accepted",
            }
        }, {"X-UniPost-Operation-Id": "  "}),
        ("202 wrong code", 202, {
            "error": {"code": "WRONG_CODE", "message": "Accepted"}
        }, {"X-UniPost-Operation-Id": "op_1"}),
        ("202 missing code", 202, {
            "error": {"message": "Accepted"}
        }, {"X-UniPost-Operation-Id": "op_1"}),
        ("202 missing error object", 202, {}, {
            "X-UniPost-Operation-Id": "op_1"
        }),
        ("202 missing message", 202, {
            "error": {"code": "X_REMOTE_ACCEPTED_RECONCILING"}
        }, {"X-UniPost-Operation-Id": "op_1"}),
        ("202 unexpected data envelope", 202, {
            "data": _reply_item_payload(),
            "error": {
                "code": "X_REMOTE_ACCEPTED_RECONCILING",
                "message": "Accepted",
            },
        }, {"X-UniPost-Operation-Id": "op_1"}),
        ("200 missing data", 200, {}, {}),
        ("201 with data", 201, {"data": _reply_item_payload()}, {}),
        ("204 empty", 204, None, {}),
    ],
    ids=lambda value: value if isinstance(value, str) and value[0].isdigit() else None,
)
async def test_async_reply_malformed_success_fails_closed_after_one_request(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    status: int,
    body: object,
    headers: dict[str, str],
):
    def handler(_request: httpx.Request) -> httpx.Response:
        if body is None:
            return httpx.Response(status, headers=headers)
        return httpx.Response(status, headers=headers, json=body)

    requests, _client_options = _install_async_transport(monkeypatch, handler)

    with pytest.raises(
        ValueError,
        match=rf"^Failed to decode Inbox reply response with status {status}\.$",
    ):
        await _async_client().inbox.workspace().reply("item_1", text="Thanks")

    assert requests, case
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        b'{"api_key":"up_test_inbox_secret"',
        b"up_test_inbox_secret_adjacent\xff",
    ],
)
async def test_async_reply_malformed_encoding_fails_closed_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: httpx.Response(
            202,
            headers={"X-UniPost-Operation-Id": "op_1"},
            content=content,
        ),
    )

    with pytest.raises(ValueError) as raised:
        await _async_client().inbox.workspace().reply(
            "item_1",
            text="Thanks",
            idempotency_key="idem-secret-value",
        )

    assert len(requests) == 1
    assert str(raised.value) == "Failed to decode Inbox reply response."
    representation = repr(raised.value)
    assert "up_test_inbox_secret" not in representation
    assert "idem-secret-value" not in representation


@pytest.mark.asyncio
async def test_async_reply_signature_matches_sync():
    scoped = _async_client().inbox.workspace()
    sync_scoped = Inbox(FakeHTTP()).workspace()

    assert inspect.signature(scoped.reply) == inspect.signature(sync_scoped.reply)


def _async_error_response(
    status: int,
    code: str,
    *,
    normalized_code: str = "NORMALIZED",
    retry_after: object = 0,
    retry_after_header: str = "0",
) -> httpx.Response:
    body = {
        "error": {
            "code": code,
            "normalized_code": normalized_code,
            "message": "Reply failed",
            "retry_after": retry_after,
        }
    }
    return httpx.Response(
        status,
        headers={
            "Content-Type": "application/json",
            "Retry-After": retry_after_header,
        },
        content=json.dumps(body).encode("utf-8"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, "VALIDATION_ERROR"),
        (402, "X_MONTHLY_USAGE_LIMIT_EXCEEDED"),
        (409, "X_RECONNECT_REQUIRED"),
        (409, "NEEDS_RECONNECT"),
        (409, "IDEMPOTENCY_KEY_CONFLICT"),
        (409, "X_WRITE_OUTCOME_PENDING"),
        (409, "X_WRITE_NEEDS_RECONCILIATION"),
        (409, "X_USAGE_REVERSAL_PENDING"),
        (422, "VALIDATION_ERROR"),
        (422, "PLATFORM_ERROR"),
    ],
)
async def test_async_reply_non_2xx_preserves_raw_code_after_one_request(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    code: str,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: _async_error_response(
            status,
            code,
            normalized_code="NORMALIZED_DIFFERENT",
        ),
    )

    with pytest.raises(UniPostError) as raised:
        await _async_client().inbox.workspace().reply("item_1", text="Thanks")

    assert len(requests) == 1
    assert raised.value.status == status
    assert raised.value.code == code


@pytest.mark.asyncio
async def test_async_ordinary_request_keeps_normalized_code_precedence(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: _async_error_response(
            409,
            "RAW_CODE",
            normalized_code="NORMALIZED_CODE",
        ),
    )
    http = _async_client().inbox._http

    with pytest.raises(UniPostError) as raised:
        await http.request("POST", "/ordinary")

    assert len(requests) == 1
    assert raised.value.code == "NORMALIZED_CODE"


@pytest.mark.asyncio
async def test_async_ordinary_request_still_returns_body_only(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: httpx.Response(200, json={"data": "ok"}),
    )

    result = await _async_client().inbox._http.request("GET", "/ordinary")

    assert len(requests) == 1
    assert result == {"data": "ok"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b'\xef\xbb\xbf{"data":"utf8-bom"}', {"data": "utf8-bom"}),
        (
            json.dumps({"data": "utf16"}).encode("utf-16"),
            {"data": "utf16"},
        ),
    ],
)
async def test_async_ordinary_request_preserves_httpx_json_encoding_compatibility(
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
    expected: dict[str, str],
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=content,
        ),
    )

    result = await _async_client().inbox._http.request("GET", "/ordinary")

    assert len(requests) == 1
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("retry_after_header", "expected_delay"),
    [
        ("up_test_retry_header_secret", 1),
        ("1000000000", 60),
    ],
)
async def test_async_ordinary_request_sanitizes_retry_header_and_retries_once(
    monkeypatch: pytest.MonkeyPatch,
    retry_after_header: str,
    expected_delay: int,
):
    outcomes = iter(
        [
            _async_error_response(
                429,
                "RATE_LIMITED",
                retry_after_header=retry_after_header,
            ),
            httpx.Response(200, json={"data": "ok"}),
        ]
    )
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: next(outcomes),
    )
    sleeps: list[object] = []

    async def fake_sleep(delay: object) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    result = await _async_client().inbox._http.request("GET", "/ordinary")

    assert result == {"data": "ok"}
    assert len(requests) == 2
    assert sleeps == [expected_delay]


@pytest.mark.asyncio
async def test_async_reply_429_is_not_slept_or_replayed(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: _async_error_response(
            429,
            "RATE_LIMITED",
            retry_after_header="up_test_retry_header_secret",
        ),
    )
    sleeps: list[object] = []

    async def fake_sleep(delay: object) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    with pytest.raises(RateLimitError):
        await _async_client().inbox.workspace().reply("item_1", text="Thanks")

    assert len(requests) == 1
    assert sleeps == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("retry_after", "expected_retry_after"),
    [
        ("up_test_retry_secret", 1),
        (["up_test_retry_secret"], 1),
        ({"marker": "up_test_retry_secret"}, 1),
        (10**9, 60),
        (float("inf"), 1),
        ("NaN", 1),
        (True, 1),
    ],
)
async def test_async_reply_429_sanitizes_malformed_retry_after_body(
    monkeypatch: pytest.MonkeyPatch,
    retry_after: object,
    expected_retry_after: int,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: _async_error_response(
            429,
            "RATE_LIMITED",
            retry_after=retry_after,
        ),
    )
    sleeps: list[object] = []

    async def fake_sleep(delay: object) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    with pytest.raises(RateLimitError) as raised:
        await _async_client().inbox.workspace().reply("item_1", text="Thanks")

    assert len(requests) == 1
    assert sleeps == []
    assert raised.value.status == 429
    assert raised.value.retry_after == expected_retry_after
    assert "up_test_retry_secret" not in repr(raised.value)


@pytest.mark.asyncio
async def test_async_reply_does_not_follow_redirect_or_make_second_request(
    monkeypatch: pytest.MonkeyPatch,
):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/capture":
            return httpx.Response(200, json={"data": _reply_item_payload()})
        return httpx.Response(
            302,
            headers={"Location": "https://redirect.example.test/capture"},
            json={"error": {"code": "REDIRECT", "message": "Redirect denied"}},
        )

    requests, _client_options = _install_async_transport(monkeypatch, handler)

    with pytest.raises(UniPostError) as raised:
        await _async_client().inbox.workspace().reply(
            "item_1",
            text="Thanks",
            idempotency_key="idem-redirect-test",
        )

    assert raised.value.status == 302
    assert [request.url.path for request in requests] == [
        "/v1/inbox/item_1/reply"
    ]


def test_remaining_inbox_types_are_public_in_types_module():
    expected = {
        "InboxUnreadCountResult",
        "InboxMarkAllReadResult",
        "InboxMediaContext",
        "XInboxBackfillRequest",
        "InboxSyncError",
        "InboxSyncAccountDetail",
        "InboxSyncResult",
        "XInboxBackfillAccountResult",
        "XInboxBackfillInProgress",
        "XInboxBackfillConfirmationRequired",
        "XInboxBackfillCompleted",
        "XInboxBackfillResult",
        "XInboxOutboundStatus",
        "InboxWebSocketConnectionDetails",
    }

    missing = sorted(name for name in expected if not hasattr(types, name))

    assert missing == []


def test_remaining_sync_and_async_inbox_methods_have_signature_parity():
    sync_scoped = Inbox(FakeHTTP()).workspace()
    async_scoped = _async_client().inbox.workspace()
    method_names = [
        "unread_count",
        "get",
        "mark_read",
        "mark_all_read",
        "update_thread_state",
        "media_context",
        "sync",
        "x_outbound_status",
        "websocket_connection_details",
    ]

    missing_sync = [name for name in method_names if not hasattr(sync_scoped, name)]
    missing_async = [name for name in method_names if not hasattr(async_scoped, name)]

    assert missing_sync == []
    assert missing_async == []
    for name in method_names:
        assert inspect.signature(getattr(sync_scoped, name)) == inspect.signature(
            getattr(async_scoped, name)
        )


_MEDIA_CONTEXT_PAYLOAD = {
    "id": "media_1",
    "caption": "Launch day",
    "media_url": "https://cdn.example.test/media.jpg",
    "timestamp": "2026-07-22T12:00:00Z",
    "media_type": "IMAGE",
    "permalink": "https://social.example.test/post/1",
    "unknown": "ignored",
}

_OUTBOUND_STATUS_PAYLOAD = {
    "id": "operation_1",
    "status": "reconciling",
    "completion_attempts": 2,
    "reconciliation_required": True,
    "updated_at": "2026-07-22T12:00:00Z",
    "reconciliation_deadline": "2026-07-22T12:05:00Z",
    "response_inbox_item_id": "inbox_2",
    "unknown": "ignored",
}

_SYNC_PAYLOAD = {
    "new_items": 4,
    "accounts_checked": 2,
    "errors": [
        {
            "account_id": "account_2",
            "platform": "instagram",
            "step": "comments",
            "error": "permission denied",
            "unknown": "ignored",
        }
    ],
    "details": [
        {
            "account_id": "account_1",
            "platform": "instagram",
            "account_name": "UniPost",
            "media_found": 3,
            "comments_found": 4,
            "unknown": "ignored",
        }
    ],
    "unknown": "ignored",
}

_BACKFILL_DETAIL_PAYLOAD = {
    "account_id": "account_x",
    "accepted": 7,
    "suppressed": 2,
    "duplicates": 1,
    "read": 10,
    "stopped_at_boundary": True,
    "stop_reason": "lookback_boundary",
    "missing_scopes": ["dm.read"],
    "unknown": "ignored",
}


@pytest.mark.parametrize(
    ("method_name", "arguments", "path", "response_body", "type_name", "fields"),
    [
        (
            "unread_count",
            (),
            "/v1/inbox/unread-count",
            {"count": 3, "unknown": "ignored"},
            "InboxUnreadCountResult",
            {"count": 3},
        ),
        (
            "get",
            ("item /?#",),
            "/v1/inbox/item%20%2F%3F%23",
            {**_reply_item_payload(), "unknown": "ignored"},
            "InboxItem",
            _reply_item_payload(),
        ),
        (
            "media_context",
            ("item /?#",),
            "/v1/inbox/item%20%2F%3F%23/media-context",
            _MEDIA_CONTEXT_PAYLOAD,
            "InboxMediaContext",
            {key: value for key, value in _MEDIA_CONTEXT_PAYLOAD.items() if key != "unknown"},
        ),
        (
            "x_outbound_status",
            ("request /?#",),
            "/v1/inbox/x-outbound-operations/request%20%2F%3F%23",
            _OUTBOUND_STATUS_PAYLOAD,
            "XInboxOutboundStatus",
            {key: value for key, value in _OUTBOUND_STATUS_PAYLOAD.items() if key != "unknown"},
        ),
    ],
)
def test_remaining_sync_get_routes_encode_ids_and_decode_typed_results(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    arguments: tuple[str, ...],
    path: str,
    response_body: dict[str, object],
    type_name: str,
    fields: dict[str, object],
):
    requests, calls = _stub_urlopen(
        monkeypatch,
        [_StubResponse(200, {"data": response_body})],
    )

    result = getattr(_real_client().inbox.managed_user("user A"), method_name)(
        *arguments
    )

    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert urlsplit(requests[0].full_url).path == path
    assert parse_qs(urlsplit(requests[0].full_url).query) == {
        "inbox_scope": ["managed_user"],
        "external_user_id": ["user A"],
    }
    assert requests[0].data is None
    assert calls[0][2] is True
    assert isinstance(result, getattr(types, type_name))
    for name, value in fields.items():
        assert getattr(result, name) == value
    assert not hasattr(result, "unknown")


@pytest.mark.parametrize(
    "response_body",
    [
        {"count": 3},
        {},
        {"data": None},
        {"data": []},
        {"data": "up_test_response_secret"},
    ],
)
def test_sync_new_success_responses_require_a_structural_data_envelope(
    monkeypatch: pytest.MonkeyPatch,
    response_body: object,
):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [_StubResponse(200, response_body)],
    )

    with pytest.raises(ValueError) as raised:
        _real_client().inbox.workspace().unread_count()

    assert len(requests) == 1
    assert str(raised.value) == "Failed to decode Inbox response."
    assert "up_test_response_secret" not in repr(raised.value)


@pytest.mark.parametrize(
    ("method_name", "arguments", "kwargs"),
    [
        ("get", ("",), {}),
        ("get", (".",), {}),
        ("mark_read", ("..",), {}),
        ("update_thread_state", ("",), {"thread_status": "open"}),
        ("media_context", (".",), {}),
        ("x_outbound_status", ("",), {}),
        ("x_outbound_status", (".",), {}),
        ("x_outbound_status", ("..",), {}),
    ],
)
def test_remaining_sync_path_ids_reject_unsafe_segments_before_request(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    arguments: tuple[str, ...],
    kwargs: dict[str, object],
):
    requests, _calls = _stub_urlopen(monkeypatch, [])

    with pytest.raises(ValueError, match="^(item_id|request_id)"):
        getattr(_real_client().inbox.workspace(), method_name)(
            *arguments,
            **kwargs,
        )

    assert requests == []


@pytest.mark.parametrize("thread_status", ["open", "assigned", "resolved"])
@pytest.mark.parametrize("assigned_to", [None, "operator_1"])
def test_sync_update_thread_state_accepts_canonical_statuses_and_exact_body(
    monkeypatch: pytest.MonkeyPatch,
    thread_status: str,
    assigned_to: Optional[str],
):
    payload = {**_reply_item_payload(), "thread_status": thread_status}
    requests, calls = _stub_urlopen(
        monkeypatch,
        [_StubResponse(200, {"data": payload})],
    )

    result = _real_client().inbox.workspace().update_thread_state(
        "item /?#",
        thread_status=thread_status,
        assigned_to=assigned_to,
    )

    expected_body = {"thread_status": thread_status}
    if assigned_to is not None:
        expected_body["assigned_to"] = assigned_to
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert urlsplit(requests[0].full_url).path == (
        "/v1/inbox/item%20%2F%3F%23/thread-state"
    )
    assert json.loads(requests[0].data.decode("utf-8")) == expected_body
    assert calls[0][2] is False
    assert isinstance(result, types.InboxItem)
    assert result.thread_status == thread_status


def test_sync_update_thread_state_rejects_unknown_status_before_request(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _calls = _stub_urlopen(monkeypatch, [])

    with pytest.raises(ValueError, match=r"^Invalid thread_status\.$"):
        _real_client().inbox.workspace().update_thread_state(
            "item_1",
            thread_status="pending",
        )

    assert requests == []


@pytest.mark.parametrize(
    ("method_name", "arguments", "kwargs", "path", "status", "body", "expected"),
    [
        (
            "mark_read",
            ("item /?#",),
            {},
            "/v1/inbox/item%20%2F%3F%23/read",
            204,
            None,
            None,
        ),
        (
            "mark_all_read",
            (),
            {},
            "/v1/inbox/mark-all-read",
            200,
            {"marked": 5, "unknown": "ignored"},
            ("InboxMarkAllReadResult", {"marked": 5}),
        ),
        (
            "sync",
            (),
            {},
            "/v1/inbox/sync",
            200,
            _SYNC_PAYLOAD,
            (
                "InboxSyncResult",
                {"new_items": 4, "accounts_checked": 2},
            ),
        ),
    ],
)
def test_remaining_sync_post_routes_send_exact_body_and_decode_results(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    arguments: tuple[str, ...],
    kwargs: dict[str, object],
    path: str,
    status: int,
    body: object,
    expected: object,
):
    requests, calls = _stub_urlopen(
        monkeypatch,
        [
            _StubResponse(
                status,
                None if body is None else {"data": body},
            )
        ],
    )

    result = getattr(_real_client().inbox.workspace(), method_name)(
        *arguments,
        **kwargs,
    )

    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert urlsplit(requests[0].full_url).path == path
    assert parse_qs(urlsplit(requests[0].full_url).query) == {
        "inbox_scope": ["workspace"]
    }
    expected_request_body = {} if method_name == "sync" else None
    assert (
        json.loads(requests[0].data.decode("utf-8"))
        if requests[0].data is not None
        else None
    ) == expected_request_body
    assert calls[0][2] is False
    if expected is None:
        assert result is None
    else:
        type_name, expected_fields = expected
        assert isinstance(result, getattr(types, type_name))
        for name, value in expected_fields.items():
            assert getattr(result, name) == value
    if method_name == "sync":
        assert isinstance(result.errors[0], types.InboxSyncError)
        assert isinstance(result.details[0], types.InboxSyncAccountDetail)
        assert result.errors[0].error == "permission denied"
        assert result.details[0].comments_found == 4


def test_x_backfill_request_is_frozen_and_serializes_every_supplied_field(
    monkeypatch: pytest.MonkeyPatch,
):
    request = types.XInboxBackfillRequest(
        include_replies=False,
        include_dms=True,
        account_id="account_x",
        lookback_days=30,
        max_items=100,
        confirmation_token="token-exact-value",
    )
    with pytest.raises(AttributeError):
        request.confirmation_token = "changed"
    response = {
        "status": "in_progress",
        "confirmation_operation_id": "operation_x",
        "execution_lease_expires_at": "2026-07-22T12:05:00Z",
    }
    requests, calls = _stub_urlopen(
        monkeypatch,
        [_StubResponse(200, {"data": response})],
    )

    result = _real_client().inbox.workspace().sync(x_backfill=request)

    assert json.loads(requests[0].data.decode("utf-8")) == {
        "x_backfill": {
            "include_replies": False,
            "include_dms": True,
            "account_id": "account_x",
            "lookback_days": 30,
            "max_items": 100,
            "confirmation_token": "token-exact-value",
        }
    }
    assert calls[0][2] is False
    assert isinstance(result, types.XInboxBackfillInProgress)


@pytest.mark.parametrize(
    ("payload", "type_name", "discriminant"),
    [
        (
            {
                "status": "in_progress",
                "confirmation_operation_id": "operation_x",
                "execution_lease_expires_at": "2026-07-22T12:05:00Z",
                "estimated_x_credits": 12,
                "confirmation_required": False,
                "confirmation_token": "token_in_progress",
                "confirmation_expires_at": "2026-07-22T12:02:00Z",
                "accounts_checked": 1,
                "accepted": 7,
                "suppressed": 2,
                "duplicates": 1,
                "read": 10,
                "details": [_BACKFILL_DETAIL_PAYLOAD],
                "unknown": "ignored",
            },
            "XInboxBackfillInProgress",
            ("status", "in_progress"),
        ),
        (
            {
                "confirmation_required": True,
                "confirmation_token": "token_confirm",
                "confirmation_expires_at": "2026-07-22T12:02:00Z",
                "accounts_checked": 1,
                "estimated_x_credits": 12,
                "confirmation_operation_id": "operation_x",
                "execution_lease_expires_at": "2026-07-22T12:05:00Z",
                "accepted": 7,
                "suppressed": 2,
                "duplicates": 1,
                "read": 10,
                "details": [_BACKFILL_DETAIL_PAYLOAD],
                "unknown": "ignored",
            },
            "XInboxBackfillConfirmationRequired",
            ("confirmation_required", True),
        ),
        (
            {
                "confirmation_required": False,
                "accounts_checked": 1,
                "accepted": 7,
                "suppressed": 2,
                "duplicates": 1,
                "read": 10,
                "estimated_x_credits": 12,
                "confirmation_operation_id": "operation_x",
                "confirmation_token": "token_completed",
                "confirmation_expires_at": "2026-07-22T12:02:00Z",
                "execution_lease_expires_at": "2026-07-22T12:05:00Z",
                "details": [_BACKFILL_DETAIL_PAYLOAD],
                "unknown": "ignored",
            },
            "XInboxBackfillCompleted",
            ("confirmation_required", False),
        ),
    ],
)
def test_sync_decodes_each_exact_x_backfill_discriminant_and_nested_details(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
    type_name: str,
    discriminant: tuple[str, object],
):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [_StubResponse(200, {"data": payload})],
    )

    result = _real_client().inbox.workspace().sync(
        x_backfill=types.XInboxBackfillRequest(
            include_replies=True,
            include_dms=False,
        )
    )

    assert len(requests) == 1
    assert isinstance(result, getattr(types, type_name))
    assert getattr(result, discriminant[0]) == discriminant[1]
    assert result.details is not None
    assert isinstance(result.details[0], types.XInboxBackfillAccountResult)
    assert result.details[0].missing_scopes == ["dm.read"]
    assert not hasattr(result, "unknown")


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "in_progress"},
        {"status": "queued", "confirmation_required": False},
        {"confirmation_required": True, "accounts_checked": 1},
        {
            "confirmation_required": False,
            "accounts_checked": 1,
            "accepted": 1,
        },
        {"confirmation_required": "false"},
    ],
)
def test_sync_x_backfill_missing_or_invalid_structure_fails_closed_safely(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [_StubResponse(200, {"data": payload})],
    )

    with pytest.raises(ValueError) as raised:
        _real_client().inbox.workspace().sync(
            x_backfill=types.XInboxBackfillRequest(
                include_replies=True,
                include_dms=True,
                confirmation_token="token-must-not-leak",
            )
        )

    assert len(requests) == 1
    assert str(raised.value) == "Failed to decode Inbox response."
    assert "token-must-not-leak" not in repr(raised.value)


@pytest.mark.parametrize(
    ("method_name", "arguments", "kwargs"),
    [
        ("reply", ("item_1",), {"text": "Thanks"}),
        ("mark_read", ("item_1",), {}),
        ("mark_all_read", (), {}),
        (
            "update_thread_state",
            ("item_1",),
            {"thread_status": "resolved"},
        ),
        ("sync", (), {}),
    ],
)
@pytest.mark.parametrize("failure_kind", ["rate_limit", "redirect"])
def test_every_sync_inbox_write_is_single_attempt_and_never_follows_redirects(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    arguments: tuple[str, ...],
    kwargs: dict[str, object],
    failure_kind: str,
):
    error = (
        _http_error(429, "RATE_LIMITED")
        if failure_kind == "rate_limit"
        else _http_error(302, "REDIRECT")
    )
    requests, calls = _stub_urlopen(monkeypatch, [error])
    sleeps: list[object] = []
    monkeypatch.setattr("unipost.http.time.sleep", sleeps.append)

    with pytest.raises(UniPostError):
        getattr(_real_client().inbox.workspace(), method_name)(
            *arguments,
            **kwargs,
        )

    assert len(requests) == 1
    assert calls[0][2] is False
    assert sleeps == []


def test_non_reply_sync_write_uses_ordinary_error_code_precedence(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _calls = _stub_urlopen(
        monkeypatch,
        [
            _http_error(
                409,
                "RAW_WRITE_CODE",
                normalized_code="NORMALIZED_WRITE_CODE",
            )
        ],
    )

    with pytest.raises(UniPostError) as raised:
        _real_client().inbox.workspace().mark_read("item_1")

    assert len(requests) == 1
    assert raised.value.code == "NORMALIZED_WRITE_CODE"


@pytest.mark.parametrize("scheme", ["https", "http"])
@pytest.mark.parametrize("scope", ["workspace", "managed_user"])
def test_sync_websocket_details_are_local_scoped_secret_safe_and_immutable(
    monkeypatch: pytest.MonkeyPatch,
    scheme: str,
    scope: str,
):
    monkeypatch.setattr(
        "unipost.http._open_request",
        lambda *_args, **_kwargs: pytest.fail("network request was not expected"),
    )
    client = UniPost(
        api_key="up_test_websocket_secret",
        base_url=f"{scheme}://api.example.test/base?ignored=yes#fragment",
    )
    scoped = (
        client.inbox.workspace()
        if scope == "workspace"
        else client.inbox.managed_user("user A")
    )

    first = scoped.websocket_connection_details()
    second = scoped.websocket_connection_details()

    expected_scheme = "wss" if scheme == "https" else "ws"
    assert urlsplit(first.url).scheme == expected_scheme
    assert urlsplit(first.url).netloc == "api.example.test"
    assert urlsplit(first.url).path == "/v1/inbox/ws"
    expected_query = {"inbox_scope": [scope]}
    if scope == "managed_user":
        expected_query["external_user_id"] = ["user A"]
    assert parse_qs(urlsplit(first.url).query) == expected_query
    assert "up_test_websocket_secret" not in first.url
    assert dict(first.headers) == {
        "Authorization": "Bearer up_test_websocket_secret"
    }
    assert first is not second
    assert first.headers is not second.headers
    with pytest.raises(TypeError):
        first.headers["Authorization"] = "changed"
    with pytest.raises(AttributeError):
        first.url = "changed"


@pytest.mark.parametrize(
    "base_url",
    [
        "ftp://api.example.test/up_test_invalid_secret",
        "api.example.test/up_test_invalid_secret",
        "https:///up_test_invalid_secret",
        "https://api.example.test:not-a-port/up_test_invalid_secret",
        "https://api example.test/up_test_invalid_secret",
    ],
)
def test_sync_websocket_invalid_base_fails_with_fixed_safe_error(base_url: str):
    scoped = UniPost(
        api_key="up_test_websocket_secret",
        base_url=base_url,
    ).inbox.workspace()

    with pytest.raises(ValueError) as raised:
        scoped.websocket_connection_details()

    assert str(raised.value) == "Invalid WebSocket base URL."
    assert "secret" not in repr(raised.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "arguments", "path", "response_body", "type_name", "fields"),
    [
        (
            "unread_count",
            (),
            "/v1/inbox/unread-count",
            {"count": 3, "unknown": "ignored"},
            "InboxUnreadCountResult",
            {"count": 3},
        ),
        (
            "get",
            ("item /?#",),
            "/v1/inbox/item /?#",
            {**_reply_item_payload(), "unknown": "ignored"},
            "InboxItem",
            _reply_item_payload(),
        ),
        (
            "media_context",
            ("item /?#",),
            "/v1/inbox/item /?#/media-context",
            _MEDIA_CONTEXT_PAYLOAD,
            "InboxMediaContext",
            {key: value for key, value in _MEDIA_CONTEXT_PAYLOAD.items() if key != "unknown"},
        ),
        (
            "x_outbound_status",
            ("request /?#",),
            "/v1/inbox/x-outbound-operations/request /?#",
            _OUTBOUND_STATUS_PAYLOAD,
            "XInboxOutboundStatus",
            {key: value for key, value in _OUTBOUND_STATUS_PAYLOAD.items() if key != "unknown"},
        ),
    ],
)
async def test_remaining_async_get_routes_encode_ids_and_decode_typed_results(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    arguments: tuple[str, ...],
    path: str,
    response_body: dict[str, object],
    type_name: str,
    fields: dict[str, object],
):
    requests, client_options = _install_async_transport(
        monkeypatch,
        lambda _request: httpx.Response(200, json={"data": response_body}),
    )

    result = await getattr(
        _async_client().inbox.managed_user("user A"),
        method_name,
    )(*arguments)

    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == path
    expected_raw_paths = {
        "get": b"/v1/inbox/item%20%2F%3F%23",
        "media_context": b"/v1/inbox/item%20%2F%3F%23/media-context",
        "x_outbound_status": (
            b"/v1/inbox/x-outbound-operations/request%20%2F%3F%23"
        ),
    }
    if method_name in expected_raw_paths:
        assert requests[0].url.raw_path.split(b"?")[0] == expected_raw_paths[
            method_name
        ]
    assert parse_qs(requests[0].url.query.decode("ascii")) == {
        "inbox_scope": ["managed_user"],
        "external_user_id": ["user A"],
    }
    assert client_options == [{"timeout": 5, "follow_redirects": False}]
    assert isinstance(result, getattr(types, type_name))
    for name, value in fields.items():
        assert getattr(result, name) == value
    assert not hasattr(result, "unknown")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_body",
    [
        {"count": 3},
        {},
        {"data": None},
        {"data": []},
        {"data": "up_test_response_secret"},
    ],
)
async def test_async_new_success_responses_require_a_structural_data_envelope(
    monkeypatch: pytest.MonkeyPatch,
    response_body: object,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: httpx.Response(200, json=response_body),
    )

    with pytest.raises(ValueError) as raised:
        await _async_client().inbox.workspace().unread_count()

    assert len(requests) == 1
    assert str(raised.value) == "Failed to decode Inbox response."
    assert "up_test_response_secret" not in repr(raised.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "arguments", "kwargs"),
    [
        ("get", ("",), {}),
        ("get", (".",), {}),
        ("mark_read", ("..",), {}),
        ("update_thread_state", ("",), {"thread_status": "open"}),
        ("media_context", (".",), {}),
        ("x_outbound_status", ("",), {}),
        ("x_outbound_status", (".",), {}),
        ("x_outbound_status", ("..",), {}),
    ],
)
async def test_remaining_async_path_ids_reject_unsafe_segments_before_request(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    arguments: tuple[str, ...],
    kwargs: dict[str, object],
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: pytest.fail("network request was not expected"),
    )

    with pytest.raises(ValueError, match="^(item_id|request_id)"):
        await getattr(_async_client().inbox.workspace(), method_name)(
            *arguments,
            **kwargs,
        )

    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("thread_status", ["open", "assigned", "resolved"])
@pytest.mark.parametrize("assigned_to", [None, "operator_1"])
async def test_async_update_thread_state_exact_body_and_typed_result(
    monkeypatch: pytest.MonkeyPatch,
    thread_status: str,
    assigned_to: Optional[str],
):
    payload = {**_reply_item_payload(), "thread_status": thread_status}
    requests, client_options = _install_async_transport(
        monkeypatch,
        lambda _request: httpx.Response(200, json={"data": payload}),
    )

    result = await _async_client().inbox.workspace().update_thread_state(
        "item /?#",
        thread_status=thread_status,
        assigned_to=assigned_to,
    )

    expected_body = {"thread_status": thread_status}
    if assigned_to is not None:
        expected_body["assigned_to"] = assigned_to
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v1/inbox/item /?#/thread-state"
    assert json.loads(requests[0].content.decode("utf-8")) == expected_body
    assert client_options == [{"timeout": 5, "follow_redirects": False}]
    assert isinstance(result, types.InboxItem)
    assert result.thread_status == thread_status


@pytest.mark.asyncio
async def test_async_update_thread_state_rejects_unknown_status_before_request(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: pytest.fail("network request was not expected"),
    )

    with pytest.raises(ValueError, match=r"^Invalid thread_status\.$"):
        await _async_client().inbox.workspace().update_thread_state(
            "item_1",
            thread_status="pending",
        )

    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "arguments", "kwargs", "path", "status", "body", "expected"),
    [
        (
            "mark_read",
            ("item /?#",),
            {},
            "/v1/inbox/item /?#/read",
            204,
            None,
            None,
        ),
        (
            "mark_all_read",
            (),
            {},
            "/v1/inbox/mark-all-read",
            200,
            {"marked": 5, "unknown": "ignored"},
            ("InboxMarkAllReadResult", {"marked": 5}),
        ),
        (
            "sync",
            (),
            {},
            "/v1/inbox/sync",
            200,
            _SYNC_PAYLOAD,
            (
                "InboxSyncResult",
                {"new_items": 4, "accounts_checked": 2},
            ),
        ),
    ],
)
async def test_remaining_async_post_routes_exact_body_and_typed_results(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    arguments: tuple[str, ...],
    kwargs: dict[str, object],
    path: str,
    status: int,
    body: object,
    expected: object,
):
    def handler(_request: httpx.Request) -> httpx.Response:
        if body is None:
            return httpx.Response(status)
        return httpx.Response(status, json={"data": body})

    requests, client_options = _install_async_transport(monkeypatch, handler)

    result = await getattr(_async_client().inbox.workspace(), method_name)(
        *arguments,
        **kwargs,
    )

    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == path
    assert parse_qs(requests[0].url.query.decode("ascii")) == {
        "inbox_scope": ["workspace"]
    }
    expected_request_body = {} if method_name == "sync" else None
    assert (
        json.loads(requests[0].content.decode("utf-8"))
        if requests[0].content
        else None
    ) == expected_request_body
    assert client_options == [{"timeout": 5, "follow_redirects": False}]
    if expected is None:
        assert result is None
    else:
        type_name, expected_fields = expected
        assert isinstance(result, getattr(types, type_name))
        for name, value in expected_fields.items():
            assert getattr(result, name) == value
    if method_name == "sync":
        assert isinstance(result.errors[0], types.InboxSyncError)
        assert isinstance(result.details[0], types.InboxSyncAccountDetail)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "type_name"),
    [
        (
            {
                "status": "in_progress",
                "confirmation_operation_id": "operation_x",
                "execution_lease_expires_at": "2026-07-22T12:05:00Z",
                "details": [_BACKFILL_DETAIL_PAYLOAD],
            },
            "XInboxBackfillInProgress",
        ),
        (
            {
                "confirmation_required": True,
                "confirmation_token": "token_confirm",
                "confirmation_expires_at": "2026-07-22T12:02:00Z",
                "accounts_checked": 1,
                "details": [_BACKFILL_DETAIL_PAYLOAD],
            },
            "XInboxBackfillConfirmationRequired",
        ),
        (
            {
                "confirmation_required": False,
                "accounts_checked": 1,
                "accepted": 7,
                "suppressed": 2,
                "duplicates": 1,
                "read": 10,
                "details": [_BACKFILL_DETAIL_PAYLOAD],
            },
            "XInboxBackfillCompleted",
        ),
    ],
)
async def test_async_x_backfill_serialization_and_discriminated_results(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
    type_name: str,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: httpx.Response(200, json={"data": payload}),
    )

    result = await _async_client().inbox.workspace().sync(
        x_backfill=types.XInboxBackfillRequest(
            include_replies=False,
            include_dms=False,
            confirmation_token="token-exact-value",
        )
    )

    assert json.loads(requests[0].content.decode("utf-8")) == {
        "x_backfill": {
            "include_replies": False,
            "include_dms": False,
            "confirmation_token": "token-exact-value",
        }
    }
    assert isinstance(result, getattr(types, type_name))
    assert result.details is not None
    assert isinstance(result.details[0], types.XInboxBackfillAccountResult)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "arguments", "kwargs"),
    [
        ("reply", ("item_1",), {"text": "Thanks"}),
        ("mark_read", ("item_1",), {}),
        ("mark_all_read", (), {}),
        (
            "update_thread_state",
            ("item_1",),
            {"thread_status": "resolved"},
        ),
        ("sync", (), {}),
    ],
)
@pytest.mark.parametrize("failure_kind", ["rate_limit", "redirect"])
async def test_every_async_inbox_write_is_single_attempt_and_no_redirects(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    arguments: tuple[str, ...],
    kwargs: dict[str, object],
    failure_kind: str,
):
    response = (
        _async_error_response(429, "RATE_LIMITED")
        if failure_kind == "rate_limit"
        else _async_error_response(302, "REDIRECT")
    )
    requests, client_options = _install_async_transport(
        monkeypatch,
        lambda _request: response,
    )
    sleeps: list[object] = []

    async def fake_sleep(delay: object) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    with pytest.raises(UniPostError):
        await getattr(_async_client().inbox.workspace(), method_name)(
            *arguments,
            **kwargs,
        )

    assert len(requests) == 1
    assert client_options == [{"timeout": 5, "follow_redirects": False}]
    assert sleeps == []


@pytest.mark.asyncio
async def test_non_reply_async_write_uses_ordinary_error_code_precedence(
    monkeypatch: pytest.MonkeyPatch,
):
    requests, _client_options = _install_async_transport(
        monkeypatch,
        lambda _request: _async_error_response(
            409,
            "RAW_WRITE_CODE",
            normalized_code="NORMALIZED_WRITE_CODE",
        ),
    )

    with pytest.raises(UniPostError) as raised:
        await _async_client().inbox.workspace().mark_read("item_1")

    assert len(requests) == 1
    assert raised.value.code == "NORMALIZED_WRITE_CODE"


@pytest.mark.parametrize("scheme", ["https", "http"])
@pytest.mark.parametrize("scope", ["workspace", "managed_user"])
def test_async_websocket_details_are_synchronous_local_and_immutable(
    monkeypatch: pytest.MonkeyPatch,
    scheme: str,
    scope: str,
):
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *_args, **_kwargs: pytest.fail("network request was not expected"),
    )
    client = AsyncUniPost(
        api_key="up_test_websocket_secret",
        base_url=f"{scheme}://api.example.test/base?ignored=yes#fragment",
    )
    scoped = (
        client.inbox.workspace()
        if scope == "workspace"
        else client.inbox.managed_user("user A")
    )

    first = scoped.websocket_connection_details()
    second = scoped.websocket_connection_details()

    assert not inspect.isawaitable(first)
    assert urlsplit(first.url).scheme == ("wss" if scheme == "https" else "ws")
    assert urlsplit(first.url).path == "/v1/inbox/ws"
    expected_query = {"inbox_scope": [scope]}
    if scope == "managed_user":
        expected_query["external_user_id"] = ["user A"]
    assert parse_qs(urlsplit(first.url).query) == expected_query
    assert "up_test_websocket_secret" not in first.url
    assert dict(first.headers) == {
        "Authorization": "Bearer up_test_websocket_secret"
    }
    assert first is not second
    assert first.headers is not second.headers
    with pytest.raises(TypeError):
        first.headers["Authorization"] = "changed"


@pytest.mark.parametrize(
    "base_url",
    [
        "ftp://api.example.test/up_test_invalid_secret",
        "api.example.test/up_test_invalid_secret",
        "https:///up_test_invalid_secret",
        "https://api.example.test:not-a-port/up_test_invalid_secret",
        "https://api example.test/up_test_invalid_secret",
    ],
)
def test_async_websocket_invalid_base_fails_with_fixed_safe_error(base_url: str):
    scoped = AsyncUniPost(
        api_key="up_test_websocket_secret",
        base_url=base_url,
    ).inbox.workspace()

    with pytest.raises(ValueError) as raised:
        scoped.websocket_connection_details()

    assert str(raised.value) == "Invalid WebSocket base URL."
    assert "secret" not in repr(raised.value)
