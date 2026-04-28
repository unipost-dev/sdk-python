"""Plans resource."""

from __future__ import annotations
from typing import Any

from unipost.types import Plan, _from_dict


class Plans:
    def __init__(self, http: Any) -> None:
        self._http = http

    def list(self) -> list[Plan]:
        """List available subscription plans."""
        resp = self._http.get("/v1/plans")
        return [_from_dict(Plan, p) for p in resp.get("data", [])]
