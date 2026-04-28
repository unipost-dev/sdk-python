"""Delivery jobs resource."""

from __future__ import annotations
from typing import Any, Optional, Union

from unipost.types import DeliveryJob, _from_dict


class DeliveryJobs:
    def __init__(self, http: Any) -> None:
        self._http = http

    def list(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        states: Optional[Union[list[str], str]] = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if limit is not None:
            query["limit"] = limit
        if offset is not None:
            query["offset"] = offset
        if states is not None:
            query["states"] = ",".join(states) if isinstance(states, list) else states
        resp = self._http.get("/v1/post-delivery-jobs", query=query or None)
        resp["data"] = [_from_dict(DeliveryJob, j) for j in resp.get("data", [])]
        return resp

    def summary(self) -> dict[str, Any]:
        resp = self._http.get("/v1/post-delivery-jobs/summary")
        return resp["data"]

    def retry(self, job_id: str) -> DeliveryJob:
        resp = self._http.post(f"/v1/post-delivery-jobs/{job_id}/retry")
        return _from_dict(DeliveryJob, resp["data"])

    def cancel(self, job_id: str) -> DeliveryJob:
        resp = self._http.post(f"/v1/post-delivery-jobs/{job_id}/cancel")
        return _from_dict(DeliveryJob, resp["data"])
