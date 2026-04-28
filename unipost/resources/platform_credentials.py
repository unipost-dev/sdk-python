"""Platform credentials resource (BYO OAuth client_id/client_secret)."""

from __future__ import annotations
from typing import Any

from unipost.types import PlatformCredential, _from_dict


class PlatformCredentials:
    def __init__(self, http: Any) -> None:
        self._http = http

    def create(
        self,
        *,
        platform: str,
        client_id: str,
        client_secret: str,
    ) -> PlatformCredential:
        resp = self._http.post(
            "/v1/platform-credentials",
            body={
                "platform": platform,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        return _from_dict(PlatformCredential, resp["data"])

    def list(self) -> dict[str, Any]:
        resp = self._http.get("/v1/platform-credentials")
        resp["data"] = [_from_dict(PlatformCredential, p) for p in resp.get("data", [])]
        return resp

    def delete(self, platform: str) -> None:
        self._http.delete(f"/v1/platform-credentials/{platform}")
