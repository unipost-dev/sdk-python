"""Media resource."""

from __future__ import annotations
from typing import Any, Optional
from pathlib import Path

from unipost.types import AudioOverlayError, AudioOverlayJob, MediaUploadResponse, _from_dict

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".aac": "audio/aac",
    ".m4a": "audio/mp4",
}


def _normalize(data: dict[str, Any]) -> MediaUploadResponse:
    if "media_id" not in data and "id" in data:
        data["media_id"] = data["id"]
    return _from_dict(MediaUploadResponse, data)


def _normalize_audio_overlay(data: dict[str, Any]) -> AudioOverlayJob:
    payload = dict(data)
    if isinstance(payload.get("error"), dict):
        payload["error"] = _from_dict(AudioOverlayError, payload["error"])
    return _from_dict(AudioOverlayJob, payload)


class AudioOverlays:
    def __init__(self, http: Any) -> None:
        self._http = http

    def create(
        self,
        *,
        video_media_id: str,
        audio_media_id: str,
        mode: Optional[str] = None,
        video_volume: Optional[int] = None,
        audio_volume: Optional[int] = None,
        audio_start_ms: Optional[int] = None,
        fit: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> AudioOverlayJob:
        """Create an async job that combines uploaded video and audio media."""
        body: dict[str, Any] = {
            "video_media_id": video_media_id,
            "audio_media_id": audio_media_id,
        }
        for key, value in {
            "mode": mode,
            "video_volume": video_volume,
            "audio_volume": audio_volume,
            "audio_start_ms": audio_start_ms,
            "fit": fit,
        }.items():
            if value is not None:
                body[key] = value

        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        resp = self._http.post("/v1/media/audio-overlays", body=body, headers=headers)
        return _normalize_audio_overlay(resp["data"])

    def get(self, job_id: str) -> AudioOverlayJob:
        resp = self._http.get(f"/v1/media/audio-overlays/{job_id}")
        return _normalize_audio_overlay(resp["data"])


class Media:
    def __init__(self, http: Any) -> None:
        self._http = http
        self.audio_overlays = AudioOverlays(http)

    def upload(
        self,
        *,
        filename: str,
        content_type: str,
        size_bytes: Optional[int] = None,
        content_hash: Optional[str] = None,
    ) -> MediaUploadResponse:
        """Request a presigned upload URL for a media item."""
        body: dict[str, Any] = {
            "filename": filename,
            "content_type": content_type,
        }
        if size_bytes is not None:
            body["size_bytes"] = size_bytes
        if content_hash is not None:
            body["content_hash"] = content_hash
        resp = self._http.post("/v1/media", body=body)
        return _normalize(resp["data"])

    def get(self, media_id: str) -> MediaUploadResponse:
        resp = self._http.get(f"/v1/media/{media_id}")
        return _normalize(resp["data"])

    def delete(self, media_id: str) -> None:
        self._http.delete(f"/v1/media/{media_id}")

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
