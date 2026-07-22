from __future__ import annotations

from io import BytesIO
import json
from urllib.parse import parse_qs, urlsplit
from urllib.error import HTTPError

import pytest

from unipost import InboxItem, InboxListResponse, UniPost
from unipost.errors import RateLimitError, UniPostError
from unipost.http import HttpClient
from unipost.resources.inbox import Inbox
import unipost.types as types


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

    def fake_urlopen(request, *, timeout, context):
        requests.append(request)
        return StubResponse()

    monkeypatch.setattr("unipost.http.urlopen", fake_urlopen)
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

    monkeypatch.setattr("unipost.http.urlopen", lambda *_args, **_kwargs: StubResponse())
    http = HttpClient(
        api_key="up_test_inbox",
        base_url="https://api.example.test",
        timeout=5,
    )

    response = http._request_with_response("POST", "/v1/inbox/item/reply")

    assert response.status == 202
    assert response.headers == {"x-unipost-operation-id": " op_1 "}
    assert response.body == {"error": {"code": "accepted"}}


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
        headers: dict[str, str] | None = None,
        raw_body: bytes | None = None,
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


def _http_error(status: int, code: str, *, normalized_code: str = "NORMALIZED"):
    body = {
        "error": {
            "code": code,
            "normalized_code": normalized_code,
            "message": "Reply failed",
            "retry_after": 0,
        }
    }
    return HTTPError(
        "https://api.example.test/v1/inbox/item/reply",
        status,
        "Reply failed",
        {"Retry-After": "0"},
        BytesIO(json.dumps(body).encode("utf-8")),
    )


def _stub_urlopen(
    monkeypatch: pytest.MonkeyPatch,
    outcomes: list[object],
):
    requests = []
    calls = []

    def fake_urlopen(request, *, timeout, context):
        requests.append(request)
        calls.append((timeout, context))
        outcome = outcomes[len(requests) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr("unipost.http.urlopen", fake_urlopen)
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
