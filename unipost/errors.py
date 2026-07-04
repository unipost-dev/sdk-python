"""Error types for the UniPost SDK."""

from __future__ import annotations
from typing import Any, Optional


class UniPostError(Exception):
    """Base error for all UniPost API errors."""

    def __init__(
        self,
        message: str,
        status: int,
        code: str,
        *,
        error_source: Optional[str] = None,
        error_temporality: Optional[str] = None,
        provider_error: Optional[dict[str, Any]] = None,
        retry_policy: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.error_source = error_source
        self.error_temporality = error_temporality
        self.provider_error = provider_error
        self.retry_policy = retry_policy


class AuthError(UniPostError):
    """401 - API key invalid or expired."""

    def __init__(self, message: str = "Authentication failed", **contract: Any) -> None:
        super().__init__(message, 401, "auth_error", **contract)


class NotFoundError(UniPostError):
    """404 - Resource not found."""

    def __init__(self, message: str = "Resource not found", **contract: Any) -> None:
        super().__init__(message, 404, "not_found", **contract)


class ValidationError(UniPostError):
    """422 - Validation error."""

    def __init__(
        self,
        message: str = "Validation failed",
        errors: Optional[dict[str, list[str]]] = None,
        **contract: Any,
    ) -> None:
        super().__init__(message, 422, "validation_error", **contract)
        self.errors = errors or {}


class RateLimitError(UniPostError):
    """429 - Rate limit exceeded."""

    def __init__(
        self,
        retry_after: int = 1,
        message: str = "Rate limit exceeded",
        **contract: Any,
    ) -> None:
        super().__init__(message, 429, "rate_limit", **contract)
        self.retry_after = retry_after


class PlatformError(UniPostError):
    """Platform-side error (e.g. Twitter rejected the post)."""

    def __init__(self, message: str, platform: str, **contract: Any) -> None:
        super().__init__(message, 502, "platform_error", **contract)
        self.platform = platform


class QuotaError(UniPostError):
    """Monthly quota exceeded."""

    def __init__(self, message: str = "Monthly quota exceeded", **contract: Any) -> None:
        super().__init__(message, 403, "quota_exceeded", **contract)


def parse_api_error(status: int, body: dict[str, Any]) -> UniPostError:
    """Parse an API error response into the appropriate error class."""
    error = body.get("error") if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        error = {}
    msg = error.get("message", f"HTTP {status}")
    code = error.get("normalized_code") or error.get("code", "unknown")
    contract = {
        "error_source": error.get("error_source"),
        "error_temporality": error.get("error_temporality"),
        "provider_error": error.get("provider_error"),
        "retry_policy": error.get("retry_policy"),
    }

    if status == 401:
        return AuthError(msg, **contract)
    if status == 404:
        return NotFoundError(msg, **contract)
    if status == 422:
        return ValidationError(msg, error.get("errors"), **contract)
    if status == 429:
        retry_after = int(error.get("retry_after", 1) or 1)
        return RateLimitError(retry_after=retry_after, message=msg, **contract)
    if status == 403 and code == "quota_exceeded":
        return QuotaError(msg, **contract)
    if status == 502 and error.get("platform"):
        return PlatformError(msg, error["platform"], **contract)
    return UniPostError(msg, status, code, **contract)
