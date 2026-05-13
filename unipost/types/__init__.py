"""Type definitions for the UniPost SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


Platform = Literal[
    "twitter",
    "linkedin",
    "instagram",
    "threads",
    "tiktok",
    "youtube",
    "bluesky",
    "facebook",
    "pinterest",
]
AccountStatus = Literal["active", "reconnect_required", "disconnected"]
ConnectionType = Literal["byo", "managed"]
PostStatus = Literal[
    "draft",
    "scheduled",
    "queued",
    "publishing",
    "dispatching",
    "retrying",
    "processing",
    "published",
    "partial",
    "failed",
    "cancelled",
    "canceled",
]
PublishMode = Literal["now", "schedule", "queue", "draft"]
ApiKeyEnvironment = Literal["production", "test"]


@dataclass
class Workspace:
    id: str
    name: str = ""
    per_account_monthly_limit: Optional[int] = None
    usage_modes: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Profile:
    id: str
    workspace_id: str = ""
    name: Optional[str] = None
    account_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    branding_logo_url: Optional[str] = None
    branding_display_name: Optional[str] = None
    branding_primary_color: Optional[str] = None


@dataclass
class SocialAccount:
    id: str
    platform: str
    profile_id: str = ""
    profile_name: str = ""
    account_name: Optional[str] = None
    external_user_id: Optional[str] = None
    external_user_email: Optional[str] = None
    status: str = "active"
    connection_type: str = "byo"


@dataclass
class PlatformResult:
    social_account_id: str = ""
    id: Optional[str] = None
    platform: Optional[str] = None
    account_name: Optional[str] = None
    caption: Optional[str] = None
    status: str = ""
    external_id: Optional[str] = None
    url: Optional[str] = None
    error_message: Optional[str] = None
    published_at: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class Post:
    id: str
    caption: Optional[str] = None
    media_urls: list[str] = field(default_factory=list)
    status: str = ""
    execution_mode: Optional[str] = None
    queued_results_count: int = 0
    active_job_count: int = 0
    retrying_count: int = 0
    dead_count: int = 0
    created_at: str = ""
    scheduled_at: Optional[str] = None
    published_at: Optional[str] = None
    results: list[PlatformResult] = field(default_factory=list)


@dataclass
class AccountHealth:
    social_account_id: str = ""
    platform: str = ""
    status: str = ""
    last_successful_post_at: Optional[str] = None
    token_expires_at: Optional[str] = None
    last_error: Optional[dict[str, Any]] = None


@dataclass
class ConnectSession:
    id: str
    url: str = ""
    allow_quickstart_creds: bool = False
    status: str = ""
    expires_at: str = ""
    platform: str = ""
    external_user_id: str = ""
    external_user_email: Optional[str] = None
    return_url: Optional[str] = None
    created_at: str = ""
    completed_at: Optional[str] = None
    completed_social_account_id: Optional[str] = None


@dataclass
class OAuthConnectResponse:
    auth_url: str = ""


@dataclass
class ManagedUser:
    external_user_id: str
    external_user_email: Optional[str] = None
    account_count: int = 0
    platform_counts: dict[str, int] = field(default_factory=dict)
    reconnect_count: int = 0


@dataclass
class MediaUploadResponse:
    media_id: str = ""
    upload_url: str = ""
    id: Optional[str] = None
    status: str = ""
    content_type: str = ""
    size_bytes: int = 0
    download_url: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class PostAnalyticsItem:
    post_id: str = ""
    social_account_id: str = ""
    platform: str = ""
    external_id: str = ""
    impressions: int = 0
    reach: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    clicks: int = 0
    video_views: int = 0
    views: int = 0
    engagement_rate: float = 0.0
    consecutive_failures: int = 0
    last_failure_reason: Optional[str] = None


# Backwards-compat alias for v0.2.0 callers.
PostAnalytics = PostAnalyticsItem


@dataclass
class AnalyticsRollup:
    granularity: str = "day"
    group_by: list[str] = field(default_factory=list)
    series: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ApiKey:
    id: str
    name: str = ""
    prefix: str = ""
    environment: str = ""
    created_at: str = ""
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None


@dataclass
class CreatedApiKey:
    id: str
    name: str = ""
    prefix: str = ""
    environment: str = ""
    created_at: str = ""
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None
    key: str = ""


@dataclass
class PlatformCredential:
    platform: str
    client_id: str = ""
    created_at: str = ""


@dataclass
class WebhookSubscription:
    id: str
    name: str = ""
    url: str = ""
    events: list[str] = field(default_factory=list)
    active: bool = True
    secret: Optional[str] = None
    secret_preview: str = ""
    created_at: str = ""


@dataclass
class DeliveryJob:
    id: str
    post_id: str = ""
    social_post_result_id: str = ""
    social_account_id: str = ""
    platform: str = ""
    kind: str = ""
    state: str = ""
    attempts: int = 0
    max_attempts: int = 0
    failure_stage: Optional[str] = None
    error_code: Optional[str] = None
    platform_error_code: Optional[str] = None
    last_error: Optional[str] = None
    next_run_at: Optional[str] = None
    last_attempt_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Plan:
    id: str
    name: str = ""
    price_cents: int = 0
    post_limit: int = 0


@dataclass
class Usage:
    period: str = ""
    post_count: int = 0
    post_limit: int = 0
    plan: str = ""
    percentage: float = 0.0
    warning: Optional[str] = None


@dataclass
class PaginatedResponse:
    data: list[Any] = field(default_factory=list)
    next_cursor: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


def _from_dict(cls: type, data: dict[str, Any]) -> Any:
    """Create a dataclass instance from a dict, ignoring unknown fields."""
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in field_names}
    return cls(**filtered)
