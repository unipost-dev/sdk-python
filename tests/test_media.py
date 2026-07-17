import threading

import pytest

from unipost.errors import GifConversionError
from unipost.resources.media import Media
from unipost.types import AudioOverlayJob, GifConversionJob


class FakeHTTP:
    def __init__(self):
        self.requests = []

    def post(self, path, body=None, headers=None):
        self.requests.append(("POST", path, body, headers))
        if path == "/v1/media/audio-overlays":
            return {
                "data": {
                    "id": "mpj_1",
                    "status": "queued",
                    "video_media_id": "media_video_1",
                    "audio_media_id": "media_audio_1",
                    "output_media_id": None,
                    "mode": "mix",
                    "fit": "trim_to_video",
                    "created_at": "2026-07-03T12:00:00Z",
                }
            }
        return {
            "data": {
                "id": "media_audio_1",
                "status": "reserved",
                "upload_url": "https://upload.example/audio",
            }
        }

    def get(self, path):
        self.requests.append(("GET", path, None, None))
        return {
            "data": {
                "id": "mpj_1",
                "status": "succeeded",
                "video_media_id": "media_video_1",
                "audio_media_id": "media_audio_1",
                "output_media_id": "media_output_1",
                "mode": "replace",
                "fit": "loop_to_video",
                "created_at": "2026-07-03T12:00:00Z",
                "completed_at": "2026-07-03T12:00:20Z",
            }
        }


def test_media_upload_omits_optional_size_bytes():
    http = FakeHTTP()
    media = Media(http)

    result = media.upload(filename="voiceover.mp3", content_type="audio/mpeg")

    assert result.media_id == "media_audio_1"
    assert http.requests[0] == (
        "POST",
        "/v1/media",
        {"filename": "voiceover.mp3", "content_type": "audio/mpeg"},
        None,
    )


def test_audio_overlay_create_sends_body_and_idempotency_header():
    http = FakeHTTP()
    media = Media(http)

    job = media.audio_overlays.create(
        video_media_id="media_video_1",
        audio_media_id="media_audio_1",
        mode="mix",
        video_volume=70,
        audio_volume=100,
        fit="trim_to_video",
        idempotency_key="overlay-1",
    )

    assert isinstance(job, AudioOverlayJob)
    assert job.id == "mpj_1"
    assert job.video_media_id == "media_video_1"
    assert http.requests[0] == (
        "POST",
        "/v1/media/audio-overlays",
        {
            "video_media_id": "media_video_1",
            "audio_media_id": "media_audio_1",
            "mode": "mix",
            "video_volume": 70,
            "audio_volume": 100,
            "fit": "trim_to_video",
        },
        {"Idempotency-Key": "overlay-1"},
    )


def test_audio_overlay_get_returns_job_dataclass():
    http = FakeHTTP()
    media = Media(http)

    job = media.audio_overlays.get("mpj_1")

    assert job.status == "succeeded"
    assert job.output_media_id == "media_output_1"
    assert job.completed_at == "2026-07-03T12:00:20Z"
    assert http.requests[0][1] == "/v1/media/audio-overlays/mpj_1"


class GifHTTP:
    def __init__(self, jobs=None):
        self.requests = []
        self.jobs = list(jobs or [])

    def post(self, path, body=None, headers=None):
        self.requests.append(("POST", path, body, headers))
        return {"data": self.jobs.pop(0)}

    def get(self, path):
        self.requests.append(("GET", path, None, None))
        return {"data": self.jobs.pop(0)}


def gif_job(status="queued", output_media_id=None, error=None):
    return {
        "id": "mpj_gif_1",
        "kind": "gif_to_mp4",
        "status": status,
        "gif_media_id": "media_gif_1",
        "background_color": "#FFFFFF",
        "output_profile": "universal_mp4_v1",
        "output_media_id": output_media_id,
        "created_at": "2026-07-17T12:00:00Z",
        "error": error,
    }


def test_gif_conversion_create_get_and_wait_success():
    http = GifHTTP([gif_job(), gif_job("processing"), gif_job("succeeded", "media_mp4_1")])
    media = Media(http)

    created = media.create_gif_conversion(
        gif_media_id="media_gif_1",
        background_color="#ffffff",
        idempotency_key="gif-1",
    )
    completed = media.wait_for_gif_conversion(created.id, poll_interval=0.001, timeout=1)

    assert isinstance(completed, GifConversionJob)
    assert completed.output_media_id == "media_mp4_1"
    assert http.requests[0] == (
        "POST", "/v1/media/gif-conversions",
        {"gif_media_id": "media_gif_1", "background_color": "#ffffff"},
        {"Idempotency-Key": "gif-1"},
    )


def test_gif_conversion_wait_raises_typed_terminal_error():
    http = GifHTTP([gif_job("failed", error={
        "code": "gif_decode_failed", "message": "GIF could not be decoded", "retryable": False,
    })])
    with pytest.raises(GifConversionError) as raised:
        Media(http).wait_for_gif_conversion("mpj_gif_1", poll_interval=0.001)
    assert raised.value.code == "gif_decode_failed"
    assert raised.value.retryable is False


def test_gif_conversion_wait_supports_timeout_and_cancellation():
    http = GifHTTP([gif_job("processing")])
    with pytest.raises(TimeoutError):
        Media(http).wait_for_gif_conversion("mpj_gif_1", poll_interval=0.001, timeout=0)

    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(InterruptedError):
        Media(GifHTTP([])).wait_for_gif_conversion("mpj_gif_1", cancel_event=cancelled)


def test_upload_and_convert_gif_wraps_upload_and_poll_without_publishing(monkeypatch):
    http = GifHTTP([gif_job(), gif_job("succeeded", "media_mp4_1")])
    media = Media(http)
    monkeypatch.setattr(media, "upload_file", lambda _path: "media_gif_1")

    result = media.upload_and_convert_gif(
        "animation.gif", idempotency_key="upload-gif-1", poll_interval=0.001,
    )

    assert result.output_media_id == "media_mp4_1"
    assert all("/v1/posts" not in request[1] for request in http.requests)
