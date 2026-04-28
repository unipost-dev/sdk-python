"""Accounts resource."""

from __future__ import annotations
from typing import Any, Optional

from unipost.errors import NotFoundError
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
        profile_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """List all connected social accounts."""
        query: dict[str, Any] = {}
        if platform:
            query["platform"] = platform
        if external_user_id:
            query["external_user_id"] = external_user_id
        if status:
            query["status"] = status
        if profile_id:
            query["profile_id"] = profile_id
        resp = self._http.get("/v1/accounts", query=query or None)
        resp["data"] = [_from_dict(SocialAccount, a) for a in resp.get("data", [])]
        return resp

    def get(self, account_id: str) -> SocialAccount:
        """Get a single account by ID."""
        page = self.list()
        for account in page.get("data", []):
            if getattr(account, "id", None) == account_id:
                return account
        raise NotFoundError("Account not found")

    def connect(
        self,
        *,
        platform: str,
        credentials: dict[str, str],
        profile_id: Optional[str] = None,
    ) -> SocialAccount:
        """Connect an account using BYO OAuth credentials."""
        body: dict[str, Any] = {"platform": platform, "credentials": credentials}
        if profile_id is not None:
            body["profile_id"] = profile_id
        resp = self._http.post("/v1/accounts/connect", body=body)
        return _from_dict(SocialAccount, resp["data"])

    def disconnect(self, account_id: str) -> None:
        self._http.delete(f"/v1/accounts/{account_id}")

    def capabilities(self, account_id: str) -> dict[str, Any]:
        resp = self._http.get(f"/v1/accounts/{account_id}/capabilities")
        return resp["data"]

    def health(self, account_id: str) -> AccountHealth:
        """Check connection health for an account."""
        resp = self._http.get(f"/v1/accounts/{account_id}/health")
        return _from_dict(AccountHealth, resp["data"])

    def tiktok_creator_info(self, account_id: str) -> dict[str, Any]:
        resp = self._http.get(f"/v1/accounts/{account_id}/tiktok/creator-info")
        return resp["data"]

    def facebook_page_insights(self, account_id: str) -> dict[str, Any]:
        resp = self._http.get(f"/v1/accounts/{account_id}/facebook/page-insights")
        return resp["data"]
