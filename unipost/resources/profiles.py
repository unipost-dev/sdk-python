"""Profiles resource."""

from __future__ import annotations
from typing import Any, Optional

from unipost.types import Profile, _from_dict


class Profiles:
    def __init__(self, http: Any) -> None:
        self._http = http

    def list(self) -> dict[str, Any]:
        """List all profiles in the workspace."""
        resp = self._http.get("/v1/profiles")
        resp["data"] = [_from_dict(Profile, p) for p in resp.get("data", [])]
        return resp

    def create(
        self,
        *,
        name: str,
        branding_logo_url: Optional[str] = None,
        branding_display_name: Optional[str] = None,
        branding_primary_color: Optional[str] = None,
    ) -> Profile:
        body: dict[str, Any] = {"name": name}
        if branding_logo_url is not None:
            body["branding_logo_url"] = branding_logo_url
        if branding_display_name is not None:
            body["branding_display_name"] = branding_display_name
        if branding_primary_color is not None:
            body["branding_primary_color"] = branding_primary_color
        resp = self._http.post("/v1/profiles", body=body)
        return _from_dict(Profile, resp["data"])

    def get(self, profile_id: str) -> Profile:
        """Get a single profile by ID."""
        resp = self._http.get(f"/v1/profiles/{profile_id}")
        return _from_dict(Profile, resp["data"])

    def update(
        self,
        profile_id: str,
        *,
        name: Optional[str] = None,
        branding_logo_url: Optional[str] = None,
        branding_display_name: Optional[str] = None,
        branding_primary_color: Optional[str] = None,
    ) -> Profile:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if branding_logo_url is not None:
            body["branding_logo_url"] = branding_logo_url
        if branding_display_name is not None:
            body["branding_display_name"] = branding_display_name
        if branding_primary_color is not None:
            body["branding_primary_color"] = branding_primary_color
        resp = self._http.patch(f"/v1/profiles/{profile_id}", body=body)
        return _from_dict(Profile, resp["data"])

    def delete(self, profile_id: str) -> None:
        self._http.delete(f"/v1/profiles/{profile_id}")
