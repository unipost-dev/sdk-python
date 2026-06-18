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
    Workspace,
    SocialAccount,
    Profile,
    Post,
    PlatformResult,
    AccountHealth,
    ConnectSession,
    OAuthConnectResponse,
    ManagedUser,
    PostAnalytics,
    PostAnalyticsItem,
    AnalyticsRollup,
    ApiKey,
    CreatedApiKey,
    PlatformCredential,
    WebhookSubscription,
    DeliveryJob,
    Plan,
    Usage,
    MediaUploadResponse,
)
from unipost.resources.profiles import Profiles
from unipost.resources.api_keys import ApiKeys
from unipost.resources.logs import Logs

__version__ = "0.3.0"
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
    "Workspace",
    "SocialAccount",
    "Profile",
    "Profiles",
    "Post",
    "PlatformResult",
    "AccountHealth",
    "ConnectSession",
    "OAuthConnectResponse",
    "ManagedUser",
    "PostAnalytics",
    "PostAnalyticsItem",
    "AnalyticsRollup",
    "ApiKey",
    "ApiKeys",
    "Logs",
    "CreatedApiKey",
    "PlatformCredential",
    "WebhookSubscription",
    "DeliveryJob",
    "Plan",
    "Usage",
    "MediaUploadResponse",
]
