"""Asynchronous UniPost client (requires httpx)."""

from __future__ import annotations
import os
from typing import Any, Optional

from unipost.errors import parse_api_error

DEFAULT_BASE_URL = "https://api.unipost.dev"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 2
SDK_VERSION = "0.2.5"


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
        import httpx
        import asyncio

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
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.request(
                    method,
                    url,
                    headers=req_headers,
                    json=body,
                    params=params,
                )
                if resp.is_success:
                    if resp.status_code == 204:
                        return None
                    return resp.json()
                if resp.status_code == 429 and attempt < MAX_RETRIES:
                    retry_after = int(resp.headers.get("Retry-After", "1"))
                    await asyncio.sleep(retry_after)
                    last_error = parse_api_error(resp.status_code, _safe_json(resp))
                    continue
                raise parse_api_error(resp.status_code, _safe_json(resp))

        raise last_error or Exception("Request failed after retries")

    async def get(self, path: str, query: Optional[dict[str, Any]] = None) -> Any:
        return await self.request("GET", path, query=query)

    async def post(self, path: str, body: Any = None, headers: Optional[dict[str, str]] = None) -> Any:
        return await self.request("POST", path, body=body, headers=headers)

    async def patch(self, path: str, body: Any = None) -> Any:
        return await self.request("PATCH", path, body=body)

    async def put(self, path: str, body: Any = None) -> Any:
        return await self.request("PUT", path, body=body)

    async def delete(self, path: str) -> Any:
        return await self.request("DELETE", path)


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
        self.api_keys = _AsyncApiKeys(http)
