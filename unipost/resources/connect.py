"""Connect resource (managed OAuth sessions)."""

from __future__ import annotations
from typing import Any, Optional

from unipost.types import ConnectSession, OAuthConnectResponse, _from_dict


class Connect:
    def __init__(self, http: Any) -> None:
        self._http = http

    def get_connect_url(
        self,
        *,
        profile_id: str,
        platform: str,
        redirect_url: Optional[str] = None,
    ) -> OAuthConnectResponse:
        body: dict[str, Any] = {
            "profile_id": profile_id,
            "platform": platform,
        }
        if redirect_url is not None:
            body["redirect_url"] = redirect_url
        resp = self._http.post("/v1/oauth/connect", body=body)
        return _from_dict(OAuthConnectResponse, resp["data"])

    def create_session(
        self,
        *,
        platform: str,
        external_user_id: str,
        external_user_email: Optional[str] = None,
        return_url: Optional[str] = None,
        profile_id: Optional[str] = None,
        allow_quickstart_creds: Optional[bool] = None,
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
        if allow_quickstart_creds is not None:
            body["allow_quickstart_creds"] = allow_quickstart_creds
        resp = self._http.post("/v1/connect/sessions", body=body)
        return _from_dict(ConnectSession, resp["data"])

    def get_session(self, session_id: str) -> ConnectSession:
        resp = self._http.get(f"/v1/connect/sessions/{session_id}")
        return _from_dict(ConnectSession, resp["data"])
