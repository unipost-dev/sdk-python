"""API keys resource."""

from __future__ import annotations
from typing import Any, Optional

from unipost.types import ApiKey, CreatedApiKey, _from_dict


class ApiKeys:
    def __init__(self, http: Any) -> None:
        self._http = http

    def list(self) -> dict[str, Any]:
        """List API keys for the authenticated workspace."""
        resp = self._http.get("/v1/api-keys")
        resp["data"] = [_from_dict(ApiKey, k) for k in resp.get("data", [])]
        return resp

    def create(
        self,
        *,
        name: str,
        environment: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> CreatedApiKey:
        """
        Create a new API key. The plaintext ``key`` field is only returned
        in this response; store it before navigating away.
        """
        body: dict[str, Any] = {"name": name}
        if environment is not None:
            body["environment"] = environment
        if expires_at is not None:
            body["expires_at"] = expires_at
        resp = self._http.post("/v1/api-keys", body=body)
        return _from_dict(CreatedApiKey, resp["data"])

    def revoke(self, key_id: str) -> None:
        """Revoke an API key. Subsequent requests with it will fail with 401."""
        self._http.delete(f"/v1/api-keys/{key_id}")
