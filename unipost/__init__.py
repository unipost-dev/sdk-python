"""Official UniPost API client for Python."""

from unipost.client import UniPost
from unipost.async_client import AsyncUniPost
from unipost.errors import (
    UniPostError,
    AuthError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    PlatformError,
    QuotaError,
)
from unipost.webhook import verify_webhook_signature
from unipost.types import (
    SocialAccount,
    Post,
    PlatformResult,
    ConnectSession,
    ManagedUser,
    PostAnalytics,
    AnalyticsRollup,
)

__version__ = "0.1.0"
__all__ = [
    "UniPost",
    "AsyncUniPost",
    "UniPostError",
    "AuthError",
    "NotFoundError",
    "ValidationError",
    "RateLimitError",
    "PlatformError",
    "QuotaError",
    "verify_webhook_signature",
    "SocialAccount",
    "Post",
    "PlatformResult",
    "ConnectSession",
    "ManagedUser",
    "PostAnalytics",
    "AnalyticsRollup",
]
