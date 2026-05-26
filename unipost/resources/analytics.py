"""Analytics resource."""

from __future__ import annotations
from typing import Any, Optional

from unipost.types import AnalyticsRollup, _from_dict


def _query(
    *,
    from_date: Optional[str],
    to_date: Optional[str],
    profile_id: Optional[str],
    platform: Optional[str],
    status: Optional[str],
) -> dict[str, Any]:
    q: dict[str, Any] = {}
    if from_date:
        q["from"] = from_date
    if to_date:
        q["to"] = to_date
    if profile_id:
        q["profile_id"] = profile_id
    if platform:
        q["platform"] = platform
    if status:
        q["status"] = status
    return q


def _posts_query(
    *,
    from_date: Optional[str],
    to_date: Optional[str],
    profile_id: Optional[str],
    platform: Optional[str],
    status: Optional[str],
    account_id: Optional[str],
    post_id: Optional[str],
    sort: Optional[str],
    limit: Optional[int],
    cursor: Optional[str],
) -> dict[str, Any]:
    q = _query(
        from_date=from_date,
        to_date=to_date,
        profile_id=profile_id,
        platform=platform,
        status=status,
    )
    if account_id:
        q["account_id"] = account_id
    if post_id:
        q["post_id"] = post_id
    if sort:
        q["sort"] = sort
    if limit is not None:
        q["limit"] = limit
    if cursor:
        q["cursor"] = cursor
    return q


def _platform_query(
    *,
    from_date: Optional[str],
    to_date: Optional[str],
    profile_id: Optional[str],
) -> dict[str, Any]:
    q: dict[str, Any] = {}
    if from_date:
        q["from"] = from_date
    if to_date:
        q["to"] = to_date
    if profile_id:
        q["profile_id"] = profile_id
    return q


class Analytics:
    def __init__(self, http: Any) -> None:
        self._http = http

    def summary(
        self,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        profile_id: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict[str, Any]:
        resp = self._http.get(
            "/v1/analytics/summary",
            query=_query(
                from_date=from_date,
                to_date=to_date,
                profile_id=profile_id,
                platform=platform,
                status=status,
            )
            or None,
        )
        return resp["data"]

    def trend(
        self,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        profile_id: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict[str, Any]:
        resp = self._http.get(
            "/v1/analytics/trend",
            query=_query(
                from_date=from_date,
                to_date=to_date,
                profile_id=profile_id,
                platform=platform,
                status=status,
            )
            or None,
        )
        return resp["data"]

    def by_platform(
        self,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        profile_id: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        resp = self._http.get(
            "/v1/analytics/by-platform",
            query=_query(
                from_date=from_date,
                to_date=to_date,
                profile_id=profile_id,
                platform=platform,
                status=status,
            )
            or None,
        )
        return resp.get("data") or []

    def rollup(
        self,
        *,
        from_date: str,
        to_date: str,
        granularity: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> AnalyticsRollup:
        query: dict[str, Any] = {"from": from_date, "to": to_date}
        if granularity:
            query["granularity"] = granularity
        if group_by:
            query["group_by"] = group_by
        resp = self._http.get("/v1/analytics/rollup", query=query)
        return _from_dict(AnalyticsRollup, resp["data"])

    def posts(
        self,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        profile_id: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        account_id: Optional[str] = None,
        post_id: Optional[str] = None,
        sort: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._http.get(
            "/v1/analytics/posts",
            query=_posts_query(
                from_date=from_date,
                to_date=to_date,
                profile_id=profile_id,
                platform=platform,
                status=status,
                account_id=account_id,
                post_id=post_id,
                sort=sort,
                limit=limit,
                cursor=cursor,
            )
            or None,
        )

    def export_posts_csv(
        self,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        profile_id: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        account_id: Optional[str] = None,
        post_id: Optional[str] = None,
        sort: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> str:
        return self._http.get_text(
            "/v1/analytics/posts/export",
            query=_posts_query(
                from_date=from_date,
                to_date=to_date,
                profile_id=profile_id,
                platform=platform,
                status=status,
                account_id=account_id,
                post_id=post_id,
                sort=sort,
                limit=limit,
                cursor=cursor,
            )
            or None,
        )

    def platforms(
        self,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        profile_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        resp = self._http.get(
            "/v1/analytics/platforms",
            query=_platform_query(from_date=from_date, to_date=to_date, profile_id=profile_id) or None,
        )
        return resp.get("data") or []

    def platform(
        self,
        platform: str,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        profile_id: Optional[str] = None,
    ) -> dict[str, Any]:
        resp = self._http.get(
            f"/v1/analytics/platforms/{platform}",
            query=_platform_query(from_date=from_date, to_date=to_date, profile_id=profile_id) or None,
        )
        return resp["data"]

    def refresh(
        self,
        *,
        platform: Optional[str] = None,
        profile_id: Optional[str] = None,
        account_id: Optional[str] = None,
        post_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if platform:
            body["platform"] = platform
        if profile_id:
            body["profile_id"] = profile_id
        if account_id:
            body["account_id"] = account_id
        if post_id:
            body["post_id"] = post_id
        if from_date:
            body["from"] = from_date
        if to_date:
            body["to"] = to_date
        if limit is not None:
            body["limit"] = limit
        resp = self._http.post("/v1/analytics/refresh", body=body or None)
        return resp["data"]
