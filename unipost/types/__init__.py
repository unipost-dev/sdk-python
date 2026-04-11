"""Type definitions for the UniPost SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


Platform = Literal[
    "twitter", "linkedin", "instagram", "threads", "tiktok", "youtube", "bluesky"
]
AccountStatus = Literal["active", "reconnect_required", "disconnected"]
ConnectionType = Literal["byo", "managed"]
PostStatus = Literal[
    "draft", "scheduled", "processing", "published", "partial", "failed", "cancelled"
]
PublishMode = Literal["now", "schedule", "queue", "draft"]


@dataclass
class Profile:
    id: str
    name: Optional[str] = None
    created_at: str = ""


@dataclass
class SocialAccount:
    id: str
    platform: str
    profile_id: str = ""
    account_name: Optional[str] = None
    external_user_id: Optional[str] = None
    external_user_email: Optional[str] = None
    connected_at: str = ""
    status: str = "active"
    connection_type: str = "byo"


@dataclass
class PlatformResult:
    social_account_id: str
    platform: Optional[str] = None
    account_name: Optional[str] = None
    status: str = ""
    external_id: Optional[str] = None
    error_message: Optional[str] = None
    published_at: Optional[str] = None


@dataclass
class Post:
    id: str
    caption: Optional[str] = None
    status: str = ""
    scheduled_at: Optional[str] = None
    created_at: str = ""
    published_at: Optional[str] = None
    results: list[PlatformResult] = field(default_factory=list)


@dataclass
class AccountHealth:
    account_id: str
    status: str  # "ok" | "degraded" | "disconnected"
    last_checked_at: str = ""
    error: Optional[str] = None


@dataclass
class ConnectSession:
    id: str
    url: str
    status: str  # "pending" | "completed" | "expired"
    expires_at: str = ""
    platform: str = ""
    external_user_id: str = ""


@dataclass
class ManagedUser:
    external_user_id: str
    external_user_email: Optional[str] = None
    accounts: list[SocialAccount] = field(default_factory=list)
    created_at: str = ""


@dataclass
class MediaUploadResponse:
    media_id: str
    upload_url: str


@dataclass
class PostAnalytics:
    post_id: str
    impressions: int = 0
    engagements: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    clicks: int = 0
    results: dict[str, dict[str, int]] = field(default_factory=dict)


@dataclass
class AnalyticsBucket:
    key: str
    impressions: int = 0
    engagements: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    clicks: int = 0


@dataclass
class AnalyticsRollup:
    from_date: str
    to_date: str
    granularity: str = "day"
    buckets: list[AnalyticsBucket] = field(default_factory=list)


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
