import asyncio

import pytest

from unipost.async_client import _AsyncMedia
from unipost.errors import GifConversionError


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


class AsyncGifHTTP:
    def __init__(self, jobs):
        self.jobs = list(jobs)
        self.requests = []

    async def post(self, path, body=None, headers=None):
        self.requests.append(("POST", path, body, headers))
        return {"data": self.jobs.pop(0)}

    async def get(self, path):
        self.requests.append(("GET", path, None, None))
        return {"data": self.jobs.pop(0)}


def test_async_gif_conversion_create_and_wait():
    async def case():
        media = _AsyncMedia(AsyncGifHTTP([
            gif_job(), gif_job("processing"), gif_job("succeeded", "media_mp4_1"),
        ]))
        created = await media.create_gif_conversion(
            gif_media_id="media_gif_1", idempotency_key="gif-1",
        )
        result = await media.wait_for_gif_conversion(created.id, poll_interval=0.001)
        assert result.output_media_id == "media_mp4_1"
    asyncio.run(case())


def test_async_gif_conversion_failure_timeout_and_task_cancellation():
    async def case():
        failed = _AsyncMedia(AsyncGifHTTP([gif_job("failed", error={
            "code": "gif_decode_failed", "message": "bad gif", "retryable": False,
        })]))
        with pytest.raises(GifConversionError):
            await failed.wait_for_gif_conversion("mpj_gif_1", poll_interval=0.001)

        timed = _AsyncMedia(AsyncGifHTTP([gif_job("processing")]))
        with pytest.raises(TimeoutError):
            await timed.wait_for_gif_conversion("mpj_gif_1", timeout=0)

        waiting = _AsyncMedia(AsyncGifHTTP([gif_job("processing")]))
        task = asyncio.create_task(waiting.wait_for_gif_conversion("mpj_gif_1", poll_interval=60))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(case())


def test_async_upload_and_convert_never_publishes(monkeypatch):
    async def case():
        http = AsyncGifHTTP([gif_job(), gif_job("succeeded", "media_mp4_1")])
        media = _AsyncMedia(http)

        async def fake_upload(_path):
            return "media_gif_1"

        monkeypatch.setattr(media, "upload_file", fake_upload)
        result = await media.upload_and_convert_gif(
            "animation.gif", idempotency_key="upload-gif-1", poll_interval=0.001,
        )
        assert result.output_media_id == "media_mp4_1"
        assert all("/v1/posts" not in request[1] for request in http.requests)
    asyncio.run(case())
