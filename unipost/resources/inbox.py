"""Scoped inbox resource."""

from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Literal, Optional
from urllib.parse import quote

from unipost.types import (
    InboxItem,
    InboxListResponse,
    InboxReplyCompleted,
    InboxReplyReconciling,
    InboxReplyResult,
    InboxSource,
    _from_dict,
)


_RECONCILING_CODE = "X_REMOTE_ACCEPTED_RECONCILING"
_INVALID_IDEMPOTENCY_KEY = "Invalid idempotency_key."


def _encode_item_id(item_id: str) -> str:
    if item_id in {"", ".", ".."}:
        raise ValueError("item_id must not be empty, '.' or '..'")
    return quote(item_id, safe="")


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
        if not external_user_id.strip():
            raise ValueError("external_user_id must not be blank")
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
    _scope: Literal["managed_user", "workspace"]
    _external_user_id: Optional[str] = None

    def _scope_query(self) -> dict[str, str]:
        query: dict[str, str] = {"inbox_scope": self._scope}
        if self._external_user_id is not None:
            query["external_user_id"] = self._external_user_id
        return query

    def list(
        self,
        *,
        source: Optional[InboxSource] = None,
        is_read: Optional[bool] = None,
        is_own: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> InboxListResponse:
        query: dict[str, Any] = self._scope_query()
        if source is not None:
            query["source"] = source
        if is_read is not None:
            query["is_read"] = str(is_read).lower()
        if is_own is not None:
            query["is_own"] = str(is_own).lower()
        if limit is not None:
            query["limit"] = limit

        response = self._http.get("/v1/inbox", query=query)
        return InboxListResponse(
            data=[_from_dict(InboxItem, item) for item in response.get("data") or []],
            request_id=response.get("request_id"),
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
        try:
            response = self._http._request_with_response(
                "POST",
                f"/v1/inbox/{encoded_item_id}/reply",
                body={"text": text},
                query=self._scope_query(),
                headers=headers,
                retry_rate_limits=False,
                preserve_error_code=True,
                follow_redirects=False,
            )
        except (JSONDecodeError, UnicodeDecodeError):
            raise ValueError("Failed to decode Inbox reply response.") from None

        return _decode_reply_response(
            response.status,
            response.headers,
            response.body,
        )
