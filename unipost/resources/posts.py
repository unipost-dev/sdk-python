"""Posts resource."""

from __future__ import annotations
from typing import Any, Generator, List, Optional

from unipost.types import Post, PlatformResult, _from_dict


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
    media_ids: Optional[list[str]] = None,
    scheduled_at: Optional[str] = None,
    status: Optional[str] = None,
    archived: Optional[bool] = None,
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
    if media_ids:
        body["media_ids"] = media_ids
    if scheduled_at:
        body["scheduled_at"] = scheduled_at
    if status:
        body["status"] = status
    if archived is not None:
        body["archived"] = archived
    if platform_posts:
        body["platform_posts"] = platform_posts
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return body, headers


class Posts:
    def __init__(self, http: Any) -> None:
        self._http = http

    def create(self, **kwargs: Any) -> Post:
        body, headers = _to_snake_body(**kwargs)
        resp = self._http.post("/v1/posts", body=body, headers=headers or None)
        return _parse_post(resp["data"])

    def validate(self, **kwargs: Any) -> dict[str, Any]:
        body, _ = _to_snake_body(**kwargs)
        resp = self._http.post("/v1/posts/validate", body=body)
        return resp["data"]

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
        resp = self._http.get("/v1/posts", query=query or None)
        resp["data"] = [_parse_post(p) for p in resp.get("data", [])]
        meta = resp.get("meta") or {}
        resp["next_cursor"] = meta.get("next_cursor") or resp.get("next_cursor")
        return resp

    def list_all(self, **kwargs: Any) -> Generator[Post, None, None]:
        cursor = None
        while True:
            page = self.list(cursor=cursor, **kwargs)
            for post in page["data"]:
                yield post
            cursor = page.get("next_cursor") or page.get("nextCursor")
            if not cursor:
                break

    def get(self, post_id: str) -> Post:
        resp = self._http.get(f"/v1/posts/{post_id}")
        return _parse_post(resp["data"])

    def get_queue(self, post_id: str) -> dict[str, Any]:
        resp = self._http.get(f"/v1/posts/{post_id}/queue")
        return resp["data"]

    def analytics(self, post_id: str, *, refresh: Optional[bool] = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if refresh:
            query["refresh"] = "true"
        resp = self._http.get(f"/v1/posts/{post_id}/analytics", query=query or None)
        return resp.get("data") or []

    def publish(self, post_id: str) -> Post:
        resp = self._http.post(f"/v1/posts/{post_id}/publish")
        return _parse_post(resp["data"])

    def update(self, post_id: str, **kwargs: Any) -> Post:
        body, _ = _to_snake_body(**kwargs)
        resp = self._http.patch(f"/v1/posts/{post_id}", body=body)
        return _parse_post(resp["data"])

    def archive(self, post_id: str) -> Post:
        resp = self._http.post(f"/v1/posts/{post_id}/archive")
        return _parse_post(resp["data"])

    def restore(self, post_id: str) -> Post:
        resp = self._http.post(f"/v1/posts/{post_id}/restore")
        return _parse_post(resp["data"])

    def cancel(self, post_id: str) -> Post:
        resp = self._http.post(f"/v1/posts/{post_id}/cancel")
        return _parse_post(resp["data"])

    def delete(self, post_id: str) -> None:
        self._http.delete(f"/v1/posts/{post_id}")

    def preview_link(self, post_id: str) -> dict[str, Any]:
        resp = self._http.post(f"/v1/posts/{post_id}/preview-link")
        return resp["data"]

    def retry_result(self, post_id: str, result_id: str) -> PlatformResult:
        resp = self._http.post(f"/v1/posts/{post_id}/results/{result_id}/retry")
        return _from_dict(PlatformResult, resp["data"])

    def bulk_create(self, posts: List[dict[str, Any]]) -> list[dict[str, Any]]:
        bodies = []
        for p in posts:
            body, _ = _to_snake_body(**p)
            bodies.append(body)
        resp = self._http.post("/v1/posts/bulk", body={"posts": bodies})
        return resp.get("data") or []
