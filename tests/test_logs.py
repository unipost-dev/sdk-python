from unipost.resources.logs import Logs


class FakeHTTP:
    def __init__(self):
        self.calls = []

    def get(self, path, query=None):
        self.calls.append(("GET", path, query))
        if path == "/v1/logs":
            return {
                "data": [{"id": 110, "action": "post.publish.failed", "status": "error"}],
                "meta": {"limit": 25, "has_more": True, "next_cursor": "cur_abc"},
            }
        if path == "/v1/logs/110":
            return {"data": {"id": 110, "action": "post.publish.failed", "request_payload": None}}
        raise AssertionError(f"unexpected GET {path}")

    def stream(self, path, query=None, headers=None):
        self.calls.append(("STREAM", path, query, headers))
        return iter(
            [
                "event: log.created\n",
                "id: 110\n",
                'data: {"id":110,"action":"post.publish.failed","status":"error"}\n',
                "\n",
            ]
        )


def test_lists_logs_with_cursor_filters():
    http = FakeHTTP()
    logs = Logs(http)

    result = logs.list(
        status="error",
        level="warn",
        profile_id="prof_1",
        error_code="provider_failed",
        limit=25,
        cursor="cur_prev",
    )

    assert result["data"][0]["id"] == 110
    assert result["next_cursor"] == "cur_abc"
    assert http.calls[0] == (
        "GET",
        "/v1/logs",
        {
            "status": "error",
            "level": "warn",
            "profile_id": "prof_1",
            "error_code": "provider_failed",
            "limit": 25,
            "cursor": "cur_prev",
        },
    )


def test_gets_single_log_by_id():
    http = FakeHTTP()
    logs = Logs(http)

    result = logs.get(110)

    assert result["id"] == 110
    assert result["action"] == "post.publish.failed"
    assert http.calls[0] == ("GET", "/v1/logs/110", None)


def test_streams_sse_log_created_events():
    http = FakeHTTP()
    logs = Logs(http)

    first = next(logs.stream(status="error", after_id=109))

    assert first["id"] == 110
    assert first["action"] == "post.publish.failed"
    assert http.calls[0] == (
        "STREAM",
        "/v1/logs/stream",
        {"status": "error", "after_id": 109},
        {"Accept": "text/event-stream"},
    )
