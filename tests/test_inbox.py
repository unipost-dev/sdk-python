from __future__ import annotations

import pytest

from unipost import InboxItem, InboxListResponse, UniPost
from unipost.resources.inbox import Inbox


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
                    "text": "Hello",
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
            text="Hello",
        )
    ]
    assert not hasattr(result, "next_cursor")


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
