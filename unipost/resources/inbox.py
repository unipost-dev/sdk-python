"""Scoped inbox resource."""

from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Literal, Optional, Union
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from unipost.types import (
    InboxItem,
    InboxListResponse,
    InboxMarkAllReadResult,
    InboxMediaContext,
    InboxReplyCompleted,
    InboxReplyReconciling,
    InboxReplyResult,
    InboxSource,
    InboxSyncAccountDetail,
    InboxSyncError,
    InboxSyncResult,
    InboxThreadStatus,
    InboxUnreadCountResult,
    InboxWebSocketConnectionDetails,
    XInboxBackfillAccountResult,
    XInboxBackfillCompleted,
    XInboxBackfillConfirmationRequired,
    XInboxBackfillInProgress,
    XInboxBackfillRequest,
    XInboxBackfillResult,
    XInboxOutboundStatus,
    _from_dict,
)


_RECONCILING_CODE = "X_REMOTE_ACCEPTED_RECONCILING"
_INVALID_IDEMPOTENCY_KEY = "Invalid idempotency_key."
_INBOX_DECODE_ERROR = "Failed to decode Inbox response."
_INVALID_THREAD_STATUS = "Invalid thread_status."
_InboxScope = Literal["managed_user", "workspace"]


def _validate_managed_user_id(external_user_id: str) -> None:
    if not external_user_id.strip():
        raise ValueError("external_user_id must not be blank")


def _build_scope_query(
    scope: _InboxScope,
    external_user_id: Optional[str],
) -> dict[str, str]:
    if scope == "workspace":
        if external_user_id is not None:
            raise ValueError("workspace scope must not include external_user_id")
        return {"inbox_scope": "workspace"}
    if scope == "managed_user":
        if external_user_id is None:
            raise ValueError("managed_user scope requires external_user_id")
        _validate_managed_user_id(external_user_id)
        return {
            "inbox_scope": "managed_user",
            "external_user_id": external_user_id,
        }
    raise ValueError("Invalid inbox scope.")


def _build_list_query(
    scope_query: dict[str, str],
    *,
    source: Optional[InboxSource] = None,
    is_read: Optional[bool] = None,
    is_own: Optional[bool] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    query: dict[str, Any] = dict(scope_query)
    if source is not None:
        query["source"] = source
    if is_read is not None:
        query["is_read"] = str(is_read).lower()
    if is_own is not None:
        query["is_own"] = str(is_own).lower()
    if limit is not None:
        query["limit"] = limit
    return query


def _decode_list_response(response: Any) -> InboxListResponse:
    return InboxListResponse(
        data=[_from_dict(InboxItem, item) for item in response.get("data") or []],
        request_id=response.get("request_id"),
    )


def _encode_path_id(value: str, name: Literal["item_id", "request_id"]) -> str:
    if value in {"", ".", ".."}:
        raise ValueError(f"{name} must not be empty, '.' or '..'")
    return quote(value, safe="")


def _encode_item_id(item_id: str) -> str:
    return _encode_path_id(item_id, "item_id")


def _encode_request_id(request_id: str) -> str:
    return _encode_path_id(request_id, "request_id")


def _unwrap_data_envelope(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise ValueError(_INBOX_DECODE_ERROR)
    data = response.get("data")
    if not isinstance(data, dict):
        raise ValueError(_INBOX_DECODE_ERROR)
    return data


def _decode_dataclass(cls: type, response: Any) -> Any:
    try:
        return _from_dict(cls, _unwrap_data_envelope(response))
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError(_INBOX_DECODE_ERROR) from None


def _decode_item(response: Any) -> InboxItem:
    return _decode_dataclass(InboxItem, response)


def _decode_unread_count(response: Any) -> InboxUnreadCountResult:
    return _decode_dataclass(InboxUnreadCountResult, response)


def _decode_mark_all_read(response: Any) -> InboxMarkAllReadResult:
    return _decode_dataclass(InboxMarkAllReadResult, response)


def _decode_media_context(response: Any) -> InboxMediaContext:
    return _decode_dataclass(InboxMediaContext, response)


def _decode_x_outbound_status(response: Any) -> XInboxOutboundStatus:
    return _decode_dataclass(XInboxOutboundStatus, response)


def _decode_sync_response(response: Any) -> InboxSyncResult:
    try:
        data = _unwrap_data_envelope(response)
        errors = data["errors"]
        details = data["details"]
        if not isinstance(errors, list) or not isinstance(details, list):
            raise TypeError
        decoded = dict(data)
        decoded["errors"] = [
            _from_dict(InboxSyncError, item)
            for item in errors
            if isinstance(item, dict)
        ]
        decoded["details"] = [
            _from_dict(InboxSyncAccountDetail, item)
            for item in details
            if isinstance(item, dict)
        ]
        if len(decoded["errors"]) != len(errors):
            raise TypeError
        if len(decoded["details"]) != len(details):
            raise TypeError
        return _from_dict(InboxSyncResult, decoded)
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError(_INBOX_DECODE_ERROR) from None


def _decode_backfill_details(response: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(response)
    if "details" not in decoded or decoded["details"] is None:
        return decoded
    details = decoded["details"]
    if not isinstance(details, list):
        raise TypeError
    decoded["details"] = [
        _from_dict(XInboxBackfillAccountResult, item)
        for item in details
        if isinstance(item, dict)
    ]
    if len(decoded["details"]) != len(details):
        raise TypeError
    return decoded


def _decode_x_backfill_response(response: Any) -> XInboxBackfillResult:
    try:
        decoded = _decode_backfill_details(_unwrap_data_envelope(response))
        if "status" in decoded:
            if decoded["status"] != "in_progress":
                raise ValueError
            confirmation_required = decoded.get("confirmation_required")
            if (
                confirmation_required is not None
                and confirmation_required is not False
            ):
                raise ValueError
            decoded.pop("status")
            return _from_dict(XInboxBackfillInProgress, decoded)

        confirmation_required = decoded.get("confirmation_required")
        decoded.pop("confirmation_required", None)
        if confirmation_required is True:
            return _from_dict(XInboxBackfillConfirmationRequired, decoded)
        if confirmation_required is False:
            return _from_dict(XInboxBackfillCompleted, decoded)
        raise ValueError
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError(_INBOX_DECODE_ERROR) from None


def _serialize_x_backfill_request(
    request: XInboxBackfillRequest,
) -> dict[str, Any]:
    serialized: dict[str, Any] = {
        "include_replies": request.include_replies,
        "include_dms": request.include_dms,
    }
    for name in (
        "account_id",
        "lookback_days",
        "max_items",
        "confirmation_token",
    ):
        value = getattr(request, name)
        if value is not None:
            serialized[name] = value
    return serialized


def _build_websocket_connection_details(
    base_url: str,
    api_key: str,
    scope_query: dict[str, str],
) -> InboxWebSocketConnectionDetails:
    try:
        parts = urlsplit(base_url)
        hostname = parts.hostname
        _ = parts.port
        if (
            parts.scheme not in {"http", "https"}
            or hostname is None
            or parts.username is not None
            or parts.password is not None
            or any(
                character.isspace() or character in "/\\?#"
                for character in hostname
            )
        ):
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("Invalid WebSocket base URL.") from None

    scheme = "wss" if parts.scheme == "https" else "ws"
    return InboxWebSocketConnectionDetails(
        url=urlunsplit(
            (
                scheme,
                parts.netloc,
                "/v1/inbox/ws",
                urlencode(scope_query),
                "",
            )
        ),
        headers={"Authorization": f"Bearer {api_key}"},
    )


def _validate_idempotency_key(value: str) -> None:
    try:
        encoded = value.encode("latin-1")
    except (AttributeError, UnicodeEncodeError):
        raise ValueError(_INVALID_IDEMPOTENCY_KEY) from None
    if any(byte < 32 or 127 <= byte <= 159 for byte in encoded):
        raise ValueError(_INVALID_IDEMPOTENCY_KEY)


def _decode_reply_response(
    status: int,
    headers: dict[str, str],
    body: Any,
) -> InboxReplyResult:
    operation_id = headers.get("x-unipost-operation-id", "").strip()

    if status == 200 and isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, dict):
            try:
                item = _from_dict(InboxItem, data)
            except (TypeError, ValueError):
                pass
            else:
                return InboxReplyCompleted(
                    item=item,
                    operation_id=operation_id or None,
                )

    if (
        status == 202
        and operation_id
        and isinstance(body, dict)
        and "data" not in body
    ):
        error = body.get("error")
        request_id = body.get("request_id")
        request_id_is_valid = (
            "request_id" not in body or isinstance(request_id, str)
        )
        if (
            isinstance(error, dict)
            and error.get("code") == _RECONCILING_CODE
            and isinstance(error.get("message"), str)
            and request_id_is_valid
        ):
            return InboxReplyReconciling(
                operation_id=operation_id,
                message=error["message"],
                request_id=request_id,
            )

    raise ValueError(f"Failed to decode Inbox reply response with status {status}.")


@dataclass(frozen=True)
class Inbox:
    _http: Any

    def managed_user(self, external_user_id: str) -> _ScopedInbox:
        _validate_managed_user_id(external_user_id)
        return _ScopedInbox(
            self._http,
            _scope="managed_user",
            _external_user_id=external_user_id,
        )

    def workspace(self) -> _ScopedInbox:
        return _ScopedInbox(self._http, _scope="workspace")


@dataclass(frozen=True)
class _ScopedInbox:
    _http: Any
    _scope: _InboxScope
    _external_user_id: Optional[str] = None

    def _scope_query(self) -> dict[str, str]:
        return _build_scope_query(self._scope, self._external_user_id)

    def _post(
        self,
        path: str,
        body: Any,
        *,
        headers: Optional[dict[str, str]] = None,
        preserve_error_code: bool = False,
        decode_error_message: str = _INBOX_DECODE_ERROR,
    ) -> Any:
        try:
            return self._http._request_with_response(
                "POST",
                path,
                body=body,
                query=self._scope_query(),
                headers=headers,
                retry_rate_limits=False,
                preserve_error_code=preserve_error_code,
                follow_redirects=False,
            )
        except (JSONDecodeError, UnicodeDecodeError):
            raise ValueError(decode_error_message) from None

    def list(
        self,
        *,
        source: Optional[InboxSource] = None,
        is_read: Optional[bool] = None,
        is_own: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> InboxListResponse:
        query = _build_list_query(
            self._scope_query(),
            source=source,
            is_read=is_read,
            is_own=is_own,
            limit=limit,
        )
        response = self._http.get("/v1/inbox", query=query)
        return _decode_list_response(response)

    def unread_count(self) -> InboxUnreadCountResult:
        response = self._http.get(
            "/v1/inbox/unread-count",
            query=self._scope_query(),
        )
        return _decode_unread_count(response)

    def get(self, item_id: str) -> InboxItem:
        encoded_item_id = _encode_item_id(item_id)
        response = self._http.get(
            f"/v1/inbox/{encoded_item_id}",
            query=self._scope_query(),
        )
        return _decode_item(response)

    def mark_read(self, item_id: str) -> None:
        encoded_item_id = _encode_item_id(item_id)
        self._post(f"/v1/inbox/{encoded_item_id}/read", None)

    def mark_all_read(self) -> InboxMarkAllReadResult:
        response = self._post("/v1/inbox/mark-all-read", None)
        return _decode_mark_all_read(response.body)

    def update_thread_state(
        self,
        item_id: str,
        *,
        thread_status: InboxThreadStatus,
        assigned_to: Optional[str] = None,
    ) -> InboxItem:
        encoded_item_id = _encode_item_id(item_id)
        if thread_status not in {"open", "assigned", "resolved"}:
            raise ValueError(_INVALID_THREAD_STATUS)
        body: dict[str, str] = {"thread_status": thread_status}
        if assigned_to is not None:
            body["assigned_to"] = assigned_to
        response = self._post(
            f"/v1/inbox/{encoded_item_id}/thread-state",
            body,
        )
        return _decode_item(response.body)

    def media_context(self, item_id: str) -> InboxMediaContext:
        encoded_item_id = _encode_item_id(item_id)
        response = self._http.get(
            f"/v1/inbox/{encoded_item_id}/media-context",
            query=self._scope_query(),
        )
        return _decode_media_context(response)

    def sync(
        self,
        *,
        x_backfill: Optional[XInboxBackfillRequest] = None,
    ) -> Union[InboxSyncResult, XInboxBackfillResult]:
        body = (
            {}
            if x_backfill is None
            else {"x_backfill": _serialize_x_backfill_request(x_backfill)}
        )
        response = self._post("/v1/inbox/sync", body)
        if x_backfill is None:
            return _decode_sync_response(response.body)
        return _decode_x_backfill_response(response.body)

    def x_outbound_status(self, request_id: str) -> XInboxOutboundStatus:
        encoded_request_id = _encode_request_id(request_id)
        response = self._http.get(
            f"/v1/inbox/x-outbound-operations/{encoded_request_id}",
            query=self._scope_query(),
        )
        return _decode_x_outbound_status(response)

    def websocket_connection_details(self) -> InboxWebSocketConnectionDetails:
        return self._http._websocket_connection_details(
            query=self._scope_query(),
        )

    def reply(
        self,
        item_id: str,
        *,
        text: str,
        idempotency_key: Optional[str] = None,
    ) -> InboxReplyResult:
        encoded_item_id = _encode_item_id(item_id)
        if idempotency_key is not None:
            _validate_idempotency_key(idempotency_key)
        headers = (
            {"Idempotency-Key": idempotency_key}
            if idempotency_key is not None
            else None
        )
        response = self._post(
            f"/v1/inbox/{encoded_item_id}/reply",
            {"text": text},
            headers=headers,
            preserve_error_code=True,
            decode_error_message="Failed to decode Inbox reply response.",
        )

        return _decode_reply_response(
            response.status,
            response.headers,
            response.body,
        )
