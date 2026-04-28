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
