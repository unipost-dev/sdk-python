"""Webhook subscriptions resource."""

from __future__ import annotations
from typing import Any, List, Optional

from unipost.types import WebhookSubscription, _from_dict


class Webhooks:
    def __init__(self, http: Any) -> None:
        self._http = http

    def create(
        self,
        *,
        name: str,
        url: str,
        events: List[str],
        active: Optional[bool] = None,
        secret: Optional[str] = None,
    ) -> WebhookSubscription:
        body: dict[str, Any] = {"name": name, "url": url, "events": events}
        if active is not None:
            body["active"] = active
        if secret is not None:
            body["secret"] = secret
        resp = self._http.post("/v1/webhooks", body=body)
        return _from_dict(WebhookSubscription, resp["data"])

    def list(self) -> dict[str, Any]:
        resp = self._http.get("/v1/webhooks")
        resp["data"] = [_from_dict(WebhookSubscription, w) for w in resp.get("data", [])]
        return resp

    def get(self, webhook_id: str) -> WebhookSubscription:
        resp = self._http.get(f"/v1/webhooks/{webhook_id}")
        return _from_dict(WebhookSubscription, resp["data"])

    def update(
        self,
        webhook_id: str,
        *,
        name: Optional[str] = None,
        url: Optional[str] = None,
        events: Optional[List[str]] = None,
        active: Optional[bool] = None,
    ) -> WebhookSubscription:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if url is not None:
            body["url"] = url
        if events is not None:
            body["events"] = events
        if active is not None:
            body["active"] = active
        resp = self._http.patch(f"/v1/webhooks/{webhook_id}", body=body)
        return _from_dict(WebhookSubscription, resp["data"])

    def rotate(self, webhook_id: str) -> WebhookSubscription:
        resp = self._http.post(f"/v1/webhooks/{webhook_id}/rotate")
        return _from_dict(WebhookSubscription, resp["data"])

    def delete(self, webhook_id: str) -> None:
        self._http.delete(f"/v1/webhooks/{webhook_id}")
