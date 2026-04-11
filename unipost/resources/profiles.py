"""Profiles resource."""

from __future__ import annotations
from typing import Any, Optional

from unipost.types import Profile, _from_dict


class Profiles:
    def __init__(self, http: Any) -> None:
        self._http = http

    def list(self) -> dict[str, Any]:
        """List all profiles."""
        resp = self._http.get("/v1/profiles")
        resp["data"] = [_from_dict(Profile, p) for p in resp.get("data", [])]
        return resp

    def get(self, profile_id: str) -> Profile:
        """Get a single profile by ID."""
        resp = self._http.get(f"/v1/profiles/{profile_id}")
        return _from_dict(Profile, resp["data"])
