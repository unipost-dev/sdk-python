"""Synchronous UniPost client."""

from __future__ import annotations
import os
from typing import Optional

from unipost.http import HttpClient, DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from unipost.resources.workspace import WorkspaceApi
from unipost.resources.profiles import Profiles
from unipost.resources.accounts import Accounts
from unipost.resources.platforms import Platforms
from unipost.resources.plans import Plans
from unipost.resources.platform_credentials import PlatformCredentials
from unipost.resources.api_keys import ApiKeys
from unipost.resources.posts import Posts
from unipost.resources.delivery_jobs import DeliveryJobs
from unipost.resources.media import Media
from unipost.resources.analytics import Analytics
from unipost.resources.connect import Connect
from unipost.resources.users import Users
from unipost.resources.webhooks import Webhooks
from unipost.resources.oauth import OAuth
from unipost.resources.usage import UsageApi
from unipost.resources.logs import Logs


class UniPost:
    """
    Official UniPost API client (synchronous).

    Usage::

        from unipost import UniPost

        client = UniPost()  # reads UNIPOST_API_KEY env var
        post = client.posts.create(
            caption="Hello from UniPost!",
            account_ids=["sa_twitter_xxx"],
        )
    """

    workspace: WorkspaceApi
    profiles: Profiles
    accounts: Accounts
    platforms: Platforms
    plans: Plans
    platform_credentials: PlatformCredentials
    api_keys: ApiKeys
    posts: Posts
    delivery_jobs: DeliveryJobs
    media: Media
    analytics: Analytics
    connect: Connect
    users: Users
    webhooks: Webhooks
    oauth: OAuth
    usage: UsageApi
    logs: Logs

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
                "UniPost API key is required. Pass it as UniPost(api_key=...) "
                "or set the UNIPOST_API_KEY environment variable."
            )

        http = HttpClient(
            api_key=resolved_key,
            base_url=base_url or DEFAULT_BASE_URL,
            timeout=timeout or DEFAULT_TIMEOUT,
        )

        self.workspace = WorkspaceApi(http)
        self.profiles = Profiles(http)
        self.accounts = Accounts(http)
        self.platforms = Platforms(http)
        self.plans = Plans(http)
        self.platform_credentials = PlatformCredentials(http)
        self.api_keys = ApiKeys(http)
        self.posts = Posts(http)
        self.delivery_jobs = DeliveryJobs(http)
        self.media = Media(http)
        self.analytics = Analytics(http)
        self.connect = Connect(http)
        self.users = Users(http)
        self.webhooks = Webhooks(http)
        self.oauth = OAuth(http)
        self.usage = UsageApi(http)
        self.logs = Logs(http)
