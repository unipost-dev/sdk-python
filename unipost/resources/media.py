"""Media resource."""

from __future__ import annotations
import threading
import time
import uuid
from typing import Any, Optional
from pathlib import Path

from unipost.errors import GifConversionError
from unipost.types import (
    AudioOverlayError,
    AudioOverlayJob,
    GifConversionErrorData,
    GifConversionJob,
    MediaUploadResponse,
    _from_dict,
)

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


def _normalize_gif_conversion(data: dict[str, Any]) -> GifConversionJob:
    payload = dict(data)
    if isinstance(payload.get("error"), dict):
        payload["error"] = _from_dict(GifConversionErrorData, payload["error"])
    return _from_dict(GifConversionJob, payload)


class GifConversions:
    def __init__(self, http: Any, media: "Media") -> None:
        self._http = http
        self._media = media

    def create(
        self,
        *,
        gif_media_id: str,
        background_color: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> GifConversionJob:
        body: dict[str, Any] = {"gif_media_id": gif_media_id}
        if background_color is not None:
            body["background_color"] = background_color
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        resp = self._http.post("/v1/media/gif-conversions", body=body, headers=headers)
        return _normalize_gif_conversion(resp["data"])

    def get(self, conversion_id: str) -> GifConversionJob:
        resp = self._http.get(f"/v1/media/gif-conversions/{conversion_id}")
        return _normalize_gif_conversion(resp["data"])

    def wait(
        self,
        conversion_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
        cancel_event: Optional[threading.Event] = None,
    ) -> GifConversionJob:
        deadline = time.monotonic() + timeout
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("GIF conversion polling was cancelled")
            job = self.get(conversion_id)
            if job.status == "succeeded":
                return job
            if job.status == "failed":
                error = job.error or GifConversionErrorData(
                    code="gif_conversion_failed", message="GIF conversion failed", retryable=False
                )
                raise GifConversionError(error.code, error.message, error.retryable)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for GIF conversion {conversion_id}")
            delay = min(poll_interval, remaining)
            if cancel_event is not None:
                if cancel_event.wait(delay):
                    raise InterruptedError("GIF conversion polling was cancelled")
            else:
                time.sleep(delay)

    def upload_and_convert(
        self,
        file_path: str,
        *,
        background_color: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
        cancel_event: Optional[threading.Event] = None,
    ) -> GifConversionJob:
        gif_media_id = self._media.upload_file(file_path)
        created = self.create(
            gif_media_id=gif_media_id,
            background_color=background_color,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )
        return self.wait(
            created.id,
            poll_interval=poll_interval,
            timeout=timeout,
            cancel_event=cancel_event,
        )


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
        self.gif_conversions = GifConversions(http, self)

    def create_gif_conversion(self, **kwargs: Any) -> GifConversionJob:
        return self.gif_conversions.create(**kwargs)

    def get_gif_conversion(self, conversion_id: str) -> GifConversionJob:
        return self.gif_conversions.get(conversion_id)

    def wait_for_gif_conversion(self, conversion_id: str, **kwargs: Any) -> GifConversionJob:
        return self.gif_conversions.wait(conversion_id, **kwargs)

    def upload_and_convert_gif(self, file_path: str, **kwargs: Any) -> GifConversionJob:
        return self.gif_conversions.upload_and_convert(file_path, **kwargs)

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
