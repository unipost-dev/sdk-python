"""Platforms resource."""

from __future__ import annotations
from typing import Any


class Platforms:
    def __init__(self, http: Any) -> None:
        self._http = http

    def capabilities(self) -> dict[str, Any]:
        """Per-platform capability matrix."""
        resp = self._http.get("/v1/platforms/capabilities")
        return resp["data"]
