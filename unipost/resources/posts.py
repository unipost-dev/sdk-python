"""Posts resource."""

from __future__ import annotations
from typing import Any, Generator, Optional

from unipost.types import Post, PostAnalytics, PlatformResult, _from_dict


def _parse_post(data: dict[str, Any]) -> Post:
    post = _from_dict(Post, data)
    if data.get("results"):
        post.results = [_from_dict(PlatformResult, r) for r in data["results"]]
    return post


def _to_snake_body(
    *,
    caption: Optional[str] = None,
    account_ids: Optional[list[str]] = None,
    platform_posts: Optional[list[dict[str, Any]]] = None,
    media_urls: Optional[list[str]] = None,
    scheduled_at: Optional[str] = None,
    status: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    body: dict[str, Any] = {}
    headers: dict[str, str] = {}
    if caption is not None:
        body["caption"] = caption
    if account_ids:
        body["account_ids"] = account_ids
    if media_urls:
        body["media_urls"] = media_urls
    if scheduled_at:
        body["scheduled_at"] = scheduled_at
    if status:
        body["status"] = status
    if platform_posts:
        body["platform_posts"] = []
        for pp in platform_posts:
            entry: dict[str, Any] = {"account_id": pp["account_id"]}
            if "caption" in pp:
                entry["caption"] = pp["caption"]
            if "thread_position" in pp:
                entry["thread_position"] = pp["thread_position"]
            if "first_comment" in pp:
                entry["first_comment"] = pp["first_comment"]
            if "media_ids" in pp:
                entry["media_ids"] = pp["media_ids"]
            body["platform_posts"].append(entry)
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return body, headers


class Posts:
    def __init__(self, http: Any) -> None:
        self._http = http

    def create(self, **kwargs: Any) -> Post:
        """Create a new post."""
        body, headers = _to_snake_body(**kwargs)
        resp = self._http.post("/v1/social-posts", body=body, headers=headers or None)
        return _parse_post(resp["data"])

    def list(
        self,
        *,
        status: Optional[str] = None,
        platform: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        """List posts with optional filters."""
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        if platform:
            query["platform"] = platform
        if from_date:
            query["from"] = from_date
        if to_date:
            query["to"] = to_date
        if limit:
            query["limit"] = limit
        if cursor:
            query["cursor"] = cursor
        resp = self._http.get("/v1/social-posts", query=query or None)
        resp["data"] = [_parse_post(p) for p in resp.get("data", [])]
        return resp

    def list_all(self, **kwargs: Any) -> Generator[Post, None, None]:
        """Iterate all posts with auto-pagination."""
        cursor = None
        while True:
            page = self.list(cursor=cursor, **kwargs)
            for post in page["data"]:
                yield post
            cursor = page.get("next_cursor") or page.get("nextCursor")
            if not cursor:
                break

    def get(self, post_id: str) -> Post:
        """Get a single post by ID."""
        resp = self._http.get(f"/v1/social-posts/{post_id}")
        return _parse_post(resp["data"])

    def analytics(self, post_id: str) -> PostAnalytics:
        """Get analytics for a post."""
        resp = self._http.get(f"/v1/social-posts/{post_id}/analytics")
        return _from_dict(PostAnalytics, resp["data"])

    def publish(self, post_id: str) -> Post:
        """Publish a draft post."""
        resp = self._http.post(f"/v1/social-posts/{post_id}/publish")
        return _parse_post(resp["data"])

    def cancel(self, post_id: str) -> Post:
        """Cancel a scheduled post."""
        resp = self._http.post(f"/v1/social-posts/{post_id}/cancel")
        return _parse_post(resp["data"])

    def bulk_create(self, posts: list[dict[str, Any]]) -> list[Post]:
        """Bulk create posts (up to 50)."""
        bodies = []
        for p in posts:
            body, _ = _to_snake_body(**p)
            bodies.append(body)
        resp = self._http.post("/v1/social-posts/bulk", body=bodies)
        return [_parse_post(d) for d in resp["data"]]
