"""Internal HTTP client for the UniPost SDK."""

from __future__ import annotations

import json
import ssl
import time
from dataclasses import dataclass
from typing import Any, Iterator, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from unipost.errors import parse_api_error
from unipost.types import InboxWebSocketConnectionDetails

DEFAULT_BASE_URL = "https://api.unipost.dev"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 2
SDK_VERSION = "0.6.0"
_MAX_RETRY_AFTER_SECONDS = 60
_SENSITIVE_REDIRECT_HEADERS = {"authorization", "idempotency-key"}
_DEFAULT_PORTS = {"http": 80, "https": 443, "ftp": 21}


@dataclass(frozen=True)
class _HttpResponse:
    status: int
    headers: dict[str, str]
    body: Any


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, msg, headers, fp)


def _url_origin(url: str) -> Optional[tuple[str, str, Optional[int]]]:
    try:
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if not scheme or hostname is None:
        return None
    return (
        scheme,
        hostname.lower(),
        port if port is not None else _DEFAULT_PORTS.get(scheme),
    )


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            newurl,
        )
        source_origin = _url_origin(req.full_url)
        target_origin = _url_origin(newurl)
        if (
            source_origin is None
            or target_origin is None
            or source_origin != target_origin
        ):
            for header_store in (
                redirected.headers,
                redirected.unredirected_hdrs,
            ):
                for name in tuple(header_store):
                    if name.lower() in _SENSITIVE_REDIRECT_HEADERS:
                        del header_store[name]
        return redirected


def _open_request(
    request: Request,
    *,
    timeout: int,
    context: ssl.SSLContext,
    follow_redirects: bool,
):
    redirect_handler: HTTPRedirectHandler
    if follow_redirects:
        redirect_handler = _SafeRedirectHandler()
    else:
        redirect_handler = _NoRedirectHandler()
    opener = build_opener(HTTPSHandler(context=context), redirect_handler)
    return opener.open(request, timeout=timeout)


def _coerce_retry_after(value: Any) -> int:
    """Return a safe retry delay, capped to avoid server-controlled long sleeps."""
    if isinstance(value, bool):
        return 1
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped or not stripped.isascii() or not stripped.isdigit():
            return 1
        try:
            parsed = int(stripped)
        except ValueError:
            return 1
    else:
        return 1
    if parsed < 0:
        return 1
    return min(parsed, _MAX_RETRY_AFTER_SECONDS)


def _sanitize_rate_limit_body(body: Any) -> Any:
    if not isinstance(body, dict):
        return body
    error = body.get("error")
    if not isinstance(error, dict):
        return body
    sanitized_error = dict(error)
    sanitized_error["retry_after"] = _coerce_retry_after(error.get("retry_after", 1))
    sanitized_body = dict(body)
    sanitized_body["error"] = sanitized_error
    return sanitized_body


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
        follow_redirects: bool = True,
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
                with _open_request(
                    req,
                    timeout=self._timeout,
                    context=self._ssl_ctx,
                    follow_redirects=follow_redirects,
                ) as resp:
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
                if e.code == 429:
                    resp_body = _sanitize_rate_limit_body(resp_body)
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
                    retry_after = _coerce_retry_after(
                        e.headers.get("Retry-After", "1") if e.headers else 1
                    )
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
                with _open_request(
                    req,
                    timeout=self._timeout,
                    context=self._ssl_ctx,
                    follow_redirects=True,
                ) as resp:
                    return resp.read().decode("utf-8")
            except HTTPError as e:
                try:
                    resp_body = json.loads(e.read().decode("utf-8")) if e.fp else {}
                except Exception:
                    resp_body = {}
                if e.code == 429:
                    resp_body = _sanitize_rate_limit_body(resp_body)
                parsed_error = parse_api_error(e.code, resp_body)
                if e.code == 429 and attempt < MAX_RETRIES:
                    retry_after = _coerce_retry_after(
                        e.headers.get("Retry-After", "1") if e.headers else 1
                    )
                    time.sleep(retry_after)
                    last_error = parsed_error
                    continue
                raise parsed_error from e

        raise last_error or Exception("Request failed after retries")

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
            with _open_request(
                req,
                timeout=self._timeout,
                context=self._ssl_ctx,
                follow_redirects=True,
            ) as resp:
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
            if e.code == 429:
                resp_body = _sanitize_rate_limit_body(resp_body)
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
