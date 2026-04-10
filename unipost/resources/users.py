"""Users resource (managed users via Connect)."""

from __future__ import annotations
from typing import Any

from unipost.types import ManagedUser, SocialAccount, _from_dict


class Users:
    def __init__(self, http: Any) -> None:
        self._http = http

    def list(self) -> dict[str, Any]:
        """List all managed users."""
        resp = self._http.get("/v1/users")
        for user_data in resp.get("data", []):
            user_data["accounts"] = [
                _from_dict(SocialAccount, a) for a in user_data.get("accounts", [])
            ]
        resp["data"] = [_from_dict(ManagedUser, u) for u in resp.get("data", [])]
        return resp

    def get(self, external_user_id: str) -> ManagedUser:
        """Get a single managed user by external_user_id."""
        resp = self._http.get(f"/v1/users/{external_user_id}")
        data = resp["data"]
        data["accounts"] = [
            _from_dict(SocialAccount, a) for a in data.get("accounts", [])
        ]
        return _from_dict(ManagedUser, data)
