"""Workspace resource."""

from __future__ import annotations
from typing import Any, Optional

from unipost.types import Workspace, _from_dict


class WorkspaceApi:
    def __init__(self, http: Any) -> None:
        self._http = http

    def get(self) -> Workspace:
        """Return the workspace bound to the authenticated caller."""
        resp = self._http.get("/v1/workspace")
        return _from_dict(Workspace, resp["data"])

    def update(
        self,
        *,
        name: Optional[str] = None,
        per_account_monthly_limit: Optional[int] = None,
    ) -> Workspace:
        """Update the workspace name and/or per-account quota."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if per_account_monthly_limit is not None:
            body["per_account_monthly_limit"] = per_account_monthly_limit
        resp = self._http.patch("/v1/workspace", body=body)
        return _from_dict(Workspace, resp["data"])
