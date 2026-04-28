"""Users resource (managed users via Connect)."""

from __future__ import annotations
from typing import Any
from urllib.parse import quote

from unipost.types import ManagedUser, _from_dict


class Users:
    def __init__(self, http: Any) -> None:
        self._http = http

    def list(self) -> dict[str, Any]:
        resp = self._http.get("/v1/users")
        resp["data"] = [_from_dict(ManagedUser, u) for u in resp.get("data", [])]
        return resp

    def get(self, external_user_id: str) -> ManagedUser:
        resp = self._http.get(f"/v1/users/{quote(external_user_id, safe='')}")
        return _from_dict(ManagedUser, resp["data"])
