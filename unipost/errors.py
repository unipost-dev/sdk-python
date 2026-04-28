"""Error types for the UniPost SDK."""

from __future__ import annotations
from typing import Any, Optional


class UniPostError(Exception):
    """Base error for all UniPost API errors."""

    def __init__(self, message: str, status: int, code: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class AuthError(UniPostError):
    """401 - API key invalid or expired."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, 401, "auth_error")


class NotFoundError(UniPostError):
    """404 - Resource not found."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, 404, "not_found")


class ValidationError(UniPostError):
    """422 - Validation error."""

    def __init__(
        self,
        message: str = "Validation failed",
        errors: Optional[dict[str, list[str]]] = None,
    ) -> None:
        super().__init__(message, 422, "validation_error")
        self.errors = errors or {}


class RateLimitError(UniPostError):
    """429 - Rate limit exceeded."""

    def __init__(
        self, retry_after: int = 1, message: str = "Rate limit exceeded"
    ) -> None:
        super().__init__(message, 429, "rate_limit")
        self.retry_after = retry_after


class PlatformError(UniPostError):
    """Platform-side error (e.g. Twitter rejected the post)."""

    def __init__(self, message: str, platform: str) -> None:
        super().__init__(message, 502, "platform_error")
        self.platform = platform


class QuotaError(UniPostError):
    """Monthly quota exceeded."""

    def __init__(self, message: str = "Monthly quota exceeded") -> None:
        super().__init__(message, 403, "quota_exceeded")


def parse_api_error(status: int, body: dict[str, Any]) -> UniPostError:
    """Parse an API error response into the appropriate error class."""
    error = body.get("error") if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        error = {}
    msg = error.get("message", f"HTTP {status}")
    code = error.get("normalized_code") or error.get("code", "unknown")

    if status == 401:
        return AuthError(msg)
    if status == 404:
        return NotFoundError(msg)
    if status == 422:
        return ValidationError(msg, error.get("errors"))
    if status == 429:
        retry_after = int(error.get("retry_after", 1) or 1)
        return RateLimitError(retry_after=retry_after, message=msg)
    if status == 403 and code == "quota_exceeded":
        return QuotaError(msg)
    if status == 502 and error.get("platform"):
        return PlatformError(msg, error["platform"])
    return UniPostError(msg, status, code)
