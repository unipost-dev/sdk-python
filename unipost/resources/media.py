"""Media resource."""

from __future__ import annotations
from typing import Any
from pathlib import Path

from unipost.types import MediaUploadResponse, _from_dict

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
}


class Media:
    def __init__(self, http: Any) -> None:
        self._http = http

    def upload(
        self,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> MediaUploadResponse:
        """Request a presigned upload URL."""
        resp = self._http.post(
            "/v1/media/upload",
            body={
                "filename": filename,
                "content_type": content_type,
                "size_bytes": size_bytes,
            },
        )
        return _from_dict(MediaUploadResponse, resp["data"])

    def upload_file(self, file_path: str) -> str:
        """Upload a local file and return its media_id."""
        from urllib.request import Request, urlopen

        p = Path(file_path)
        content_type = MIME_TYPES.get(p.suffix.lower(), "application/octet-stream")
        size_bytes = p.stat().st_size

        result = self.upload(
            filename=p.name,
            content_type=content_type,
            size_bytes=size_bytes,
        )

        data = p.read_bytes()
        req = Request(
            result.upload_url,
            data=data,
            headers={"Content-Type": content_type},
            method="PUT",
        )
        urlopen(req)

        return result.media_id
