"""Scoped inbox resource."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from unipost.types import InboxItem, InboxListResponse, InboxSource, _from_dict


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

    def list(
        self,
        *,
        source: Optional[InboxSource] = None,
        is_read: Optional[bool] = None,
        is_own: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> InboxListResponse:
        query: dict[str, Any] = {"inbox_scope": self._scope}
        if self._external_user_id is not None:
            query["external_user_id"] = self._external_user_id
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
