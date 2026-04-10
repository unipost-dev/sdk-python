"""Internal HTTP client for the UniPost SDK."""

from __future__ import annotations

import json
import ssl
import time
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode

from unipost.errors import parse_api_error, RateLimitError

DEFAULT_BASE_URL = "https://api.unipost.dev"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 2


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
    """Sync HTTP client using urllib (zero dependencies)."""

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
        url = f"{self._base_url}{path}"
        if query:
            filtered = {k: str(v) for k, v in query.items() if v is not None}
            if filtered:
                url += "?" + urlencode(filtered)

        req_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "unipost-python/0.1.0",
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
                        return None
                    return json.loads(resp.read().decode("utf-8"))
            except HTTPError as e:
                resp_body = json.loads(e.read().decode("utf-8")) if e.fp else {}
                if e.code == 429 and attempt < MAX_RETRIES:
                    retry_after = int(e.headers.get("Retry-After", "1"))
                    time.sleep(retry_after)
                    last_error = parse_api_error(e.code, resp_body)
                    continue
                raise parse_api_error(e.code, resp_body) from e

        raise last_error or Exception("Request failed after retries")

    def get(self, path: str, query: Optional[dict[str, Any]] = None) -> Any:
        return self.request("GET", path, query=query)

    def post(
        self,
        path: str,
        body: Any = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        return self.request("POST", path, body=body, headers=headers)

    def put(self, path: str, body: Any = None) -> Any:
        return self.request("PUT", path, body=body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)
