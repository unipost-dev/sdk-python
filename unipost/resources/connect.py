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
        return_url: str,
    ) -> ConnectSession:
        """Create a Connect session for end-user OAuth."""
        body: dict[str, Any] = {
            "platform": platform,
            "external_user_id": external_user_id,
            "return_url": return_url,
        }
        if external_user_email:
            body["external_user_email"] = external_user_email
        resp = self._http.post("/v1/connect/sessions", body=body)
        return _from_dict(ConnectSession, resp["data"])

    def get_session(self, session_id: str) -> ConnectSession:
        """Get the status of a Connect session."""
        resp = self._http.get(f"/v1/connect/sessions/{session_id}")
        return _from_dict(ConnectSession, resp["data"])
