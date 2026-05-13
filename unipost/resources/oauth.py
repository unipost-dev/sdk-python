"""OAuth resource (dashboard-style platform OAuth flows)."""

from __future__ import annotations
from typing import Any, Optional


class OAuth:
    def __init__(self, http: Any) -> None:
        self._http = http

    def connect(
        self,
        platform: str,
        *,
        redirect_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get the auth URL to redirect the user to for the given platform."""
        body: dict[str, Any] = {"platform": platform}
        if redirect_url is not None:
            body["redirect_url"] = redirect_url
        resp = self._http.post("/v1/oauth/connect", body=body)
        return resp["data"]
