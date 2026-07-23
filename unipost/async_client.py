"""Asynchronous UniPost client (requires httpx)."""

from __future__ import annotations
from dataclasses import dataclass
import json
import os
from typing import Any, Literal, Optional, Union

from unipost.errors import parse_api_error
from unipost.resources.inbox import (
    _build_list_query,
    _build_scope_query,
    _decode_item,
    _decode_list_response,
    _decode_mark_all_read,
    _decode_media_context,
    _decode_reply_response,
    _decode_sync_response,
    _decode_unread_count,
    _decode_x_backfill_response,
    _decode_x_outbound_status,
    _encode_item_id,
    _encode_request_id,
    _serialize_x_backfill_request,
    _validate_idempotency_key,
    _validate_managed_user_id,
)
from unipost.types import (
    InboxItem,
    InboxListResponse,
    InboxMarkAllReadResult,
    InboxMediaContext,
    InboxReplyResult,
    InboxSource,
    InboxSyncResult,
    InboxThreadStatus,
    InboxUnreadCountResult,
    InboxWebSocketConnectionDetails,
    XInboxBackfillRequest,
    XInboxBackfillResult,
    XInboxOutboundStatus,
)

DEFAULT_BASE_URL = "https://api.unipost.dev"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 2
SDK_VERSION = "0.6.0"


@dataclass(frozen=True)
class _AsyncHttpResponse:
    status: int
    headers: dict[str, str]
    body: Any


class AsyncHttpClient:
    """Async HTTP client using httpx."""

    def __init__(self, api_key: str, base_url: str, timeout: int) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        query: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        return (
            await self._request_with_response(
                method,
                path,
                body=body,
                query=query,
                headers=headers,
            )
        ).body

    async def _request_with_response(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        query: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        retry_rate_limits: bool = True,
        preserve_error_code: bool = False,
        follow_redirects: bool = False,
    ) -> _AsyncHttpResponse:
        import httpx
        import asyncio
        from unipost.http import _coerce_retry_after, _sanitize_rate_limit_body

        url = f"{self._base_url}{path}"
        req_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"unipost-python/{SDK_VERSION}",
        }
        if headers:
            req_headers.update(headers)

        params = {k: str(v) for k, v in (query or {}).items() if v is not None and v != ""} or None

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=follow_redirects,
            ) as client:
                resp = await client.request(
                    method,
                    url,
                    headers=req_headers,
                    json=body,
                    params=params,
                )
                if resp.is_success:
                    if resp.status_code == 204:
                        body_value = None
                    else:
                        body_value = resp.json() if resp.content else None
                    return _AsyncHttpResponse(
                        status=resp.status_code,
                        headers={
                            str(key).lower(): str(value)
                            for key, value in resp.headers.items()
                        },
                        body=body_value,
                    )
                error_body = _safe_json(resp)
                if resp.status_code == 429:
                    error_body = _sanitize_rate_limit_body(error_body)
                parsed_error = parse_api_error(resp.status_code, error_body)
                if preserve_error_code and isinstance(error_body, dict):
                    raw_error = error_body.get("error")
                    if isinstance(raw_error, dict) and isinstance(
                        raw_error.get("code"), str
                    ):
                        parsed_error.code = raw_error["code"]
                if (
                    retry_rate_limits
                    and resp.status_code == 429
                    and attempt < MAX_RETRIES
                ):
                    retry_after = _coerce_retry_after(
                        resp.headers.get("Retry-After", "1")
                    )
                    await asyncio.sleep(retry_after)
                    last_error = parsed_error
                    continue
                raise parsed_error

        raise last_error or Exception("Request failed after retries")

    async def get(self, path: str, query: Optional[dict[str, Any]] = None) -> Any:
        return await self.request("GET", path, query=query)

    def _websocket_connection_details(
        self,
        *,
        query: dict[str, str],
    ) -> InboxWebSocketConnectionDetails:
        from unipost.resources.inbox import _build_websocket_connection_details

        return _build_websocket_connection_details(
            self._base_url,
            self._api_key,
            query,
        )

    async def post(self, path: str, body: Any = None, headers: Optional[dict[str, str]] = None) -> Any:
        return await self.request("POST", path, body=body, headers=headers)

    async def patch(self, path: str, body: Any = None) -> Any:
        return await self.request("PATCH", path, body=body)

    async def put(self, path: str, body: Any = None) -> Any:
        return await self.request("PUT", path, body=body)

    async def delete(self, path: str) -> Any:
        return await self.request("DELETE", path)

    async def stream(
        self,
        path: str,
        *,
        query: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        import httpx

        url = f"{self._base_url}{path}"
        req_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": f"unipost-python/{SDK_VERSION}",
            "Accept": "text/event-stream",
        }
        if headers:
            req_headers.update(headers)
        params = {k: str(v) for k, v in (query or {}).items() if v is not None and v != ""} or None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream("GET", url, headers=req_headers, params=params) as resp:
                if resp.is_error:
                    text = await resp.aread()
                    try:
                        import json
                        body = json.loads(text.decode("utf-8")) if text else {}
                    except Exception:
                        body = {}
                    raise parse_api_error(resp.status_code, body)
                async for line in resp.aiter_lines():
                    yield line


def _safe_json(resp: Any) -> dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {}


# Async resource wrappers (mirror the sync API for the most-used resources).


class _AsyncAccounts:
    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def list(self, **kwargs: Any) -> dict[str, Any]:
        from unipost.types import SocialAccount, _from_dict
        query: dict[str, Any] = {}
        for k in ("platform", "external_user_id", "status", "profile_id"):
            if kwargs.get(k):
                query[k] = kwargs[k]
        resp = await self._http.get("/v1/accounts", query=query or None)
        resp["data"] = [_from_dict(SocialAccount, a) for a in resp.get("data", [])]
        return resp

    async def get(self, account_id: str) -> Any:
        from unipost.errors import NotFoundError
        page = await self.list()
        for account in page.get("data", []):
            if getattr(account, "id", None) == account_id:
                return account
        raise NotFoundError("Account not found")


class _AsyncPosts:
    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def create(self, **kwargs: Any) -> Any:
        from unipost.resources.posts import _to_snake_body, _parse_post
        body, headers = _to_snake_body(**kwargs)
        resp = await self._http.post("/v1/posts", body=body, headers=headers or None)
        return _parse_post(resp["data"])

    async def list(self, **kwargs: Any) -> dict[str, Any]:
        from unipost.resources.posts import _parse_post
        query: dict[str, Any] = {}
        for k in ("status", "platform", "limit", "cursor"):
            if kwargs.get(k):
                query[k] = kwargs[k]
        if kwargs.get("from_date"):
            query["from"] = kwargs["from_date"]
        if kwargs.get("to_date"):
            query["to"] = kwargs["to_date"]
        resp = await self._http.get("/v1/posts", query=query or None)
        resp["data"] = [_parse_post(p) for p in resp.get("data", [])]
        return resp

    async def get(self, post_id: str) -> Any:
        from unipost.resources.posts import _parse_post
        resp = await self._http.get(f"/v1/posts/{post_id}")
        return _parse_post(resp["data"])

    async def publish(self, post_id: str) -> Any:
        from unipost.resources.posts import _parse_post
        resp = await self._http.post(f"/v1/posts/{post_id}/publish")
        return _parse_post(resp["data"])

    async def cancel(self, post_id: str) -> Any:
        from unipost.resources.posts import _parse_post
        resp = await self._http.post(f"/v1/posts/{post_id}/cancel")
        return _parse_post(resp["data"])


class _AsyncAudioOverlays:
    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def create(
        self,
        *,
        video_media_id: str,
        audio_media_id: str,
        mode: Optional[str] = None,
        video_volume: Optional[int] = None,
        audio_volume: Optional[int] = None,
        audio_start_ms: Optional[int] = None,
        fit: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        from unipost.resources.media import _normalize_audio_overlay

        body: dict[str, Any] = {
            "video_media_id": video_media_id,
            "audio_media_id": audio_media_id,
        }
        for key, value in {
            "mode": mode,
            "video_volume": video_volume,
            "audio_volume": audio_volume,
            "audio_start_ms": audio_start_ms,
            "fit": fit,
        }.items():
            if value is not None:
                body[key] = value
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        resp = await self._http.post("/v1/media/audio-overlays", body=body, headers=headers)
        return _normalize_audio_overlay(resp["data"])

    async def get(self, job_id: str) -> Any:
        from unipost.resources.media import _normalize_audio_overlay

        resp = await self._http.get(f"/v1/media/audio-overlays/{job_id}")
        return _normalize_audio_overlay(resp["data"])


class _AsyncMedia:
    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http
        self.audio_overlays = _AsyncAudioOverlays(http)

    async def upload(
        self,
        *,
        filename: str,
        content_type: str,
        size_bytes: Optional[int] = None,
        content_hash: Optional[str] = None,
    ) -> Any:
        from unipost.resources.media import _normalize

        body: dict[str, Any] = {
            "filename": filename,
            "content_type": content_type,
        }
        if size_bytes is not None:
            body["size_bytes"] = size_bytes
        if content_hash is not None:
            body["content_hash"] = content_hash
        resp = await self._http.post("/v1/media", body=body)
        return _normalize(resp["data"])

    async def get(self, media_id: str) -> Any:
        from unipost.resources.media import _normalize

        resp = await self._http.get(f"/v1/media/{media_id}")
        return _normalize(resp["data"])

    async def delete(self, media_id: str) -> None:
        await self._http.delete(f"/v1/media/{media_id}")


class _AsyncApiKeys:
    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def list(self) -> dict[str, Any]:
        from unipost.types import ApiKey, _from_dict
        resp = await self._http.get("/v1/api-keys")
        resp["data"] = [_from_dict(ApiKey, k) for k in resp.get("data", [])]
        return resp

    async def create(self, **kwargs: Any) -> Any:
        from unipost.types import CreatedApiKey, _from_dict
        body: dict[str, Any] = {}
        for k in ("name", "environment", "expires_at"):
            if kwargs.get(k) is not None:
                body[k] = kwargs[k]
        resp = await self._http.post("/v1/api-keys", body=body)
        return _from_dict(CreatedApiKey, resp["data"])

    async def revoke(self, key_id: str) -> None:
        await self._http.delete(f"/v1/api-keys/{key_id}")


class _AsyncLogs:
    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def list(self, **kwargs: Any) -> dict[str, Any]:
        from unipost.resources.logs import _query

        resp = await self._http.get("/v1/logs", query=_query(**kwargs) or None)
        meta = resp.get("meta") or {}
        resp["next_cursor"] = meta.get("next_cursor") or resp.get("next_cursor")
        return resp

    async def get(self, log_id: Union[int, str]) -> dict[str, Any]:
        resp = await self._http.get(f"/v1/logs/{log_id}")
        return resp["data"]

    async def stream(self, **kwargs: Any):
        import json
        from unipost.resources.logs import _query

        last_event_id = kwargs.pop("last_event_id", None)
        headers = {"Accept": "text/event-stream"}
        if last_event_id is not None:
            headers["Last-Event-ID"] = str(last_event_id)

        event_name = None
        data_lines: list[str] = []

        async for raw_line in self._http.stream("/v1/logs/stream", query=_query(**kwargs) or None, headers=headers):
            line = raw_line.rstrip("\r\n")
            if line == "":
                if data_lines:
                    raw = "\n".join(data_lines)
                    data_lines = []
                    if not event_name or event_name == "log.created":
                        yield json.loads(raw)
                    event_name = None
                continue
            if line.startswith(":"):
                continue
            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
            if field == "event":
                event_name = value
            elif field == "data":
                data_lines.append(value)

        if data_lines and (not event_name or event_name == "log.created"):
            yield json.loads("\n".join(data_lines))


@dataclass(frozen=True)
class _AsyncInbox:
    _http: AsyncHttpClient

    def managed_user(self, external_user_id: str) -> _AsyncScopedInbox:
        _validate_managed_user_id(external_user_id)
        return _AsyncScopedInbox(
            self._http,
            _scope="managed_user",
            _external_user_id=external_user_id,
        )

    def workspace(self) -> _AsyncScopedInbox:
        return _AsyncScopedInbox(self._http, _scope="workspace")


@dataclass(frozen=True)
class _AsyncScopedInbox:
    _http: AsyncHttpClient
    _scope: Literal["managed_user", "workspace"]
    _external_user_id: Optional[str] = None

    def _scope_query(self) -> dict[str, str]:
        return _build_scope_query(self._scope, self._external_user_id)

    async def _post(
        self,
        path: str,
        body: Any,
        *,
        headers: Optional[dict[str, str]] = None,
        preserve_error_code: bool = False,
        decode_error_message: str = "Failed to decode Inbox response.",
    ) -> _AsyncHttpResponse:
        try:
            return await self._http._request_with_response(
                "POST",
                path,
                body=body,
                query=self._scope_query(),
                headers=headers,
                retry_rate_limits=False,
                preserve_error_code=preserve_error_code,
                follow_redirects=False,
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError(decode_error_message) from None

    async def list(
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
        response = await self._http.get("/v1/inbox", query=query)
        return _decode_list_response(response)

    async def unread_count(self) -> InboxUnreadCountResult:
        response = await self._http.get(
            "/v1/inbox/unread-count",
            query=self._scope_query(),
        )
        return _decode_unread_count(response)

    async def get(self, item_id: str) -> InboxItem:
        encoded_item_id = _encode_item_id(item_id)
        response = await self._http.get(
            f"/v1/inbox/{encoded_item_id}",
            query=self._scope_query(),
        )
        return _decode_item(response)

    async def mark_read(self, item_id: str) -> None:
        encoded_item_id = _encode_item_id(item_id)
        await self._post(f"/v1/inbox/{encoded_item_id}/read", None)

    async def mark_all_read(self) -> InboxMarkAllReadResult:
        response = await self._post("/v1/inbox/mark-all-read", None)
        return _decode_mark_all_read(response.body)

    async def update_thread_state(
        self,
        item_id: str,
        *,
        thread_status: InboxThreadStatus,
        assigned_to: Optional[str] = None,
    ) -> InboxItem:
        encoded_item_id = _encode_item_id(item_id)
        if thread_status not in {"open", "assigned", "resolved"}:
            raise ValueError("Invalid thread_status.")
        body: dict[str, str] = {"thread_status": thread_status}
        if assigned_to is not None:
            body["assigned_to"] = assigned_to
        response = await self._post(
            f"/v1/inbox/{encoded_item_id}/thread-state",
            body,
        )
        return _decode_item(response.body)

    async def media_context(self, item_id: str) -> InboxMediaContext:
        encoded_item_id = _encode_item_id(item_id)
        response = await self._http.get(
            f"/v1/inbox/{encoded_item_id}/media-context",
            query=self._scope_query(),
        )
        return _decode_media_context(response)

    async def sync(
        self,
        *,
        x_backfill: Optional[XInboxBackfillRequest] = None,
    ) -> Union[InboxSyncResult, XInboxBackfillResult]:
        body = (
            {}
            if x_backfill is None
            else {"x_backfill": _serialize_x_backfill_request(x_backfill)}
        )
        response = await self._post("/v1/inbox/sync", body)
        if x_backfill is None:
            return _decode_sync_response(response.body)
        return _decode_x_backfill_response(response.body)

    async def x_outbound_status(
        self,
        request_id: str,
    ) -> XInboxOutboundStatus:
        encoded_request_id = _encode_request_id(request_id)
        response = await self._http.get(
            f"/v1/inbox/x-outbound-operations/{encoded_request_id}",
            query=self._scope_query(),
        )
        return _decode_x_outbound_status(response)

    def websocket_connection_details(self) -> InboxWebSocketConnectionDetails:
        return self._http._websocket_connection_details(
            query=self._scope_query(),
        )

    async def reply(
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
        response = await self._post(
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


class AsyncUniPost:
    """
    Official UniPost API client (asynchronous, requires httpx).

    Usage::

        from unipost import AsyncUniPost

        async def main():
            client = AsyncUniPost()
            post = await client.posts.create(
                caption="Hello!",
                account_ids=["sa_twitter_xxx"],
            )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("UNIPOST_API_KEY")
        if not resolved_key:
            raise ValueError(
                "UniPost API key is required. Pass it as AsyncUniPost(api_key=...) "
                "or set the UNIPOST_API_KEY environment variable."
            )

        http = AsyncHttpClient(
            api_key=resolved_key,
            base_url=base_url or DEFAULT_BASE_URL,
            timeout=timeout or DEFAULT_TIMEOUT,
        )

        self.accounts = _AsyncAccounts(http)
        self.posts = _AsyncPosts(http)
        self.media = _AsyncMedia(http)
        self.api_keys = _AsyncApiKeys(http)
        self.logs = _AsyncLogs(http)
        self.inbox = _AsyncInbox(http)
