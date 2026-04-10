"""Analytics resource."""

from __future__ import annotations
from typing import Any, Optional

from unipost.types import AnalyticsRollup, AnalyticsBucket, _from_dict


class Analytics:
    def __init__(self, http: Any) -> None:
        self._http = http

    def rollup(
        self,
        *,
        from_date: str,
        to_date: str,
        granularity: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> AnalyticsRollup:
        """Get aggregated analytics rollup."""
        query: dict[str, Any] = {"from": from_date, "to": to_date}
        if granularity:
            query["granularity"] = granularity
        if group_by:
            query["group_by"] = group_by
        resp = self._http.get("/v1/analytics/rollup", query=query)
        data = resp["data"]
        rollup = AnalyticsRollup(
            from_date=data.get("from", from_date),
            to_date=data.get("to", to_date),
            granularity=data.get("granularity", "day"),
        )
        rollup.buckets = [_from_dict(AnalyticsBucket, b) for b in data.get("buckets", [])]
        return rollup
