"""Connect resource (managed OAuth sessions)."""

from __future__ import annotations
from typing import Any, Optional

from unipost.types import ConnectSession, _from_dict


class Connect:
    def __init__(self, http: Any) -> None:
        self._http = http

    def create_session(
        self,
        *,
        platform: str,
        external_user_id: str,
        external_user_email: Optional[str] = None,
        return_url: Optional[str] = None,
        profile_id: Optional[str] = None,
    ) -> ConnectSession:
        body: dict[str, Any] = {
            "platform": platform,
            "external_user_id": external_user_id,
        }
        if external_user_email:
            body["external_user_email"] = external_user_email
        if return_url:
            body["return_url"] = return_url
        if profile_id:
            body["profile_id"] = profile_id
        resp = self._http.post("/v1/connect/sessions", body=body)
        return _from_dict(ConnectSession, resp["data"])

    def get_session(self, session_id: str) -> ConnectSession:
        resp = self._http.get(f"/v1/connect/sessions/{session_id}")
        return _from_dict(ConnectSession, resp["data"])
