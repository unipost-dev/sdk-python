from unipost.resources.media import Media
from unipost.types import AudioOverlayJob


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
