"""Internal HTTP client for the UniPost SDK."""

from __future__ import annotations

import json
import ssl
import time
from dataclasses import dataclass
from typing import Any, Iterator, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode

from unipost.errors import parse_api_error

DEFAULT_BASE_URL = "https://api.unipost.dev"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 2
SDK_VERSION = "0.5.0"


@dataclass(frozen=True)
class _HttpResponse:
    status: int
    headers: dict[str, str]
    body: Any


def _default_ssl_context() -> ssl.SSLContext:
    """Create an SSL context that works across platforms.

    Uses certifi certificates if available (common on macOS where the
    system Python may not include root CAs), otherwise falls back to
    the platform default.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


class HttpClient:
    """Sync HTTP client using urllib (zero hard dependencies beyond certifi)."""

    def __init__(self, api_key: str, base_url: str, timeout: int) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._ssl_ctx = _default_ssl_context()

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        query: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        return self._request_with_response(
            method,
            path,
            body=body,
            query=query,
            headers=headers,
        ).body

    def _request_with_response(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        query: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        retry_rate_limits: bool = True,
        preserve_error_code: bool = False,
    ) -> _HttpResponse:
        url = f"{self._base_url}{path}"
        if query:
            filtered = {k: str(v) for k, v in query.items() if v is not None and v != ""}
            if filtered:
                url += "?" + urlencode(filtered)

        req_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"unipost-python/{SDK_VERSION}",
        }
        if headers:
            req_headers.update(headers)

        data = json.dumps(body).encode("utf-8") if body is not None else None
        last_error: Optional[Exception] = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                req = Request(url, data=data, headers=req_headers, method=method)
                with urlopen(req, timeout=self._timeout, context=self._ssl_ctx) as resp:
                    if resp.status == 204:
                        body_value = None
                    else:
                        raw = resp.read().decode("utf-8")
                        body_value = json.loads(raw) if raw else None
                    return _HttpResponse(
                        status=int(resp.status),
                        headers={
                            str(key).lower(): str(value)
                            for key, value in getattr(resp, "headers", {}).items()
                        },
                        body=body_value,
                    )
            except HTTPError as e:
                try:
                    resp_body = json.loads(e.read().decode("utf-8")) if e.fp else {}
                except Exception:
                    resp_body = {}
                parsed_error = parse_api_error(e.code, resp_body)
                if preserve_error_code and isinstance(resp_body, dict):
                    error_body = resp_body.get("error")
                    if isinstance(error_body, dict) and isinstance(
                        error_body.get("code"), str
                    ):
                        parsed_error.code = error_body["code"]
                if (
                    retry_rate_limits
                    and e.code == 429
                    and attempt < MAX_RETRIES
                ):
                    retry_after = int(e.headers.get("Retry-After", "1"))
                    time.sleep(retry_after)
                    last_error = parsed_error
                    continue
                raise parsed_error from e

        raise last_error or Exception("Request failed after retries")

    def request_text(
        self,
        method: str,
        path: str,
        *,
        query: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> str:
        url = f"{self._base_url}{path}"
        if query:
            filtered = {k: str(v) for k, v in query.items() if v is not None and v != ""}
            if filtered:
                url += "?" + urlencode(filtered)

        req_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": f"unipost-python/{SDK_VERSION}",
        }
        if headers:
            req_headers.update(headers)

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                req = Request(url, headers=req_headers, method=method)
                with urlopen(req, timeout=self._timeout, context=self._ssl_ctx) as resp:
                    return resp.read().decode("utf-8")
            except HTTPError as e:
                try:
                    resp_body = json.loads(e.read().decode("utf-8")) if e.fp else {}
                except Exception:
                    resp_body = {}
                if e.code == 429 and attempt < MAX_RETRIES:
                    retry_after = int(e.headers.get("Retry-After", "1"))
                    time.sleep(retry_after)
                    last_error = parse_api_error(e.code, resp_body)
                    continue
                raise parse_api_error(e.code, resp_body) from e

        raise last_error or Exception("Request failed after retries")

    def get(self, path: str, query: Optional[dict[str, Any]] = None) -> Any:
        return self.request("GET", path, query=query)

    def get_text(self, path: str, query: Optional[dict[str, Any]] = None) -> str:
        return self.request_text("GET", path, query=query)

    def stream(
        self,
        path: str,
        *,
        query: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Iterator[str]:
        url = f"{self._base_url}{path}"
        if query:
            filtered = {k: str(v) for k, v in query.items() if v is not None and v != ""}
            if filtered:
                url += "?" + urlencode(filtered)

        req_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": f"unipost-python/{SDK_VERSION}",
            "Accept": "text/event-stream",
        }
        if headers:
            req_headers.update(headers)

        try:
            req = Request(url, headers=req_headers, method="GET")
            with urlopen(req, timeout=self._timeout, context=self._ssl_ctx) as resp:
                while True:
                    raw = resp.readline()
                    if not raw:
                        break
                    yield raw.decode("utf-8")
        except HTTPError as e:
            try:
                resp_body = json.loads(e.read().decode("utf-8")) if e.fp else {}
            except Exception:
                resp_body = {}
            raise parse_api_error(e.code, resp_body) from e

    def post(
        self,
        path: str,
        body: Any = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        return self.request("POST", path, body=body, headers=headers)

    def patch(self, path: str, body: Any = None) -> Any:
        return self.request("PATCH", path, body=body)

    def put(self, path: str, body: Any = None) -> Any:
        return self.request("PUT", path, body=body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)
