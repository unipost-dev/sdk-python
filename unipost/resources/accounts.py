"""Accounts resource."""

from __future__ import annotations
from typing import Any, Optional

from unipost.types import SocialAccount, AccountHealth, _from_dict


class Accounts:
    def __init__(self, http: Any) -> None:
        self._http = http

    def list(
        self,
        *,
        platform: Optional[str] = None,
        external_user_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict[str, Any]:
        """List all connected social accounts."""
        query: dict[str, Any] = {}
        if platform:
            query["platform"] = platform
        if external_user_id:
            query["external_user_id"] = external_user_id
        if status:
            query["status"] = status
        resp = self._http.get("/v1/social-accounts", query=query or None)
        resp["data"] = [_from_dict(SocialAccount, a) for a in resp.get("data", [])]
        return resp

    def get(self, account_id: str) -> SocialAccount:
        """Get a single account by ID."""
        resp = self._http.get(f"/v1/social-accounts/{account_id}")
        return _from_dict(SocialAccount, resp["data"])

    def health(self, account_id: str) -> AccountHealth:
        """Check account health status."""
        resp = self._http.get(f"/v1/social-accounts/{account_id}/health")
        return _from_dict(AccountHealth, resp["data"])
