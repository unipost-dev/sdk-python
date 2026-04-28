"""Usage resource (monthly post quotas)."""

from __future__ import annotations
from typing import Any

from unipost.types import Usage, _from_dict


class UsageApi:
    def __init__(self, http: Any) -> None:
        self._http = http

    def get(self) -> Usage:
        resp = self._http.get("/v1/usage")
        return _from_dict(Usage, resp["data"])
