"""Synchronous UniPost client."""

from __future__ import annotations
import os
from typing import Optional

from unipost.http import HttpClient, DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from unipost.resources.accounts import Accounts
from unipost.resources.posts import Posts
from unipost.resources.media import Media
from unipost.resources.analytics import Analytics
from unipost.resources.connect import Connect
from unipost.resources.users import Users
from unipost.resources.profiles import Profiles


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

    accounts: Accounts
    posts: Posts
    media: Media
    analytics: Analytics
    connect: Connect
    users: Users
    profiles: Profiles

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

        self.accounts = Accounts(http)
        self.posts = Posts(http)
        self.media = Media(http)
        self.analytics = Analytics(http)
        self.connect = Connect(http)
        self.users = Users(http)
        self.profiles = Profiles(http)
