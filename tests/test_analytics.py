from unipost.resources.analytics import Analytics


class FakeHTTP:
    def __init__(self):
        self.calls = []

    def get(self, path, query=None):
        self.calls.append(("GET", path, query))
        if path == "/v1/analytics/posts":
            return {
                "data": [{"post_id": "post_1", "platform": "pinterest"}],
                "meta": {"next_cursor": "25"},
            }
        if path == "/v1/analytics/platforms":
            return {"data": [{"platform": "tiktok", "health": "ready"}]}
        if path == "/v1/analytics/platforms/tiktok":
            return {"data": {"platform": "tiktok", "summary": {"posts": 3}}}
        raise AssertionError(f"unexpected GET {path}")

    def get_text(self, path, query=None):
        self.calls.append(("GET_TEXT", path, query))
        return "post_id,platform\npost_1,tiktok\n"

    def post(self, path, body=None, headers=None):
        self.calls.append(("POST", path, body, headers))
        return {"data": {"status": "queued", "matched_count": 7, "requested_count": 5, "limit": 5}}


def test_lists_analytics_posts_with_explorer_filters():
    http = FakeHTTP()
    analytics = Analytics(http)

    result = analytics.posts(
        platform="pinterest",
        account_id="sa_1",
        post_id="post_1",
        sort="engagement_rate",
        limit=25,
        cursor="0",
    )

    assert result["data"][0]["post_id"] == "post_1"
    assert result["meta"]["next_cursor"] == "25"
    assert http.calls[0] == (
        "GET",
        "/v1/analytics/posts",
        {
            "platform": "pinterest",
            "account_id": "sa_1",
            "post_id": "post_1",
            "sort": "engagement_rate",
            "limit": 25,
            "cursor": "0",
        },
    )


def test_exports_analytics_posts_as_csv_text():
    http = FakeHTTP()
    analytics = Analytics(http)

    csv = analytics.export_posts_csv(platform="tiktok")

    assert "post_id,platform" in csv
    assert http.calls[0] == ("GET_TEXT", "/v1/analytics/posts/export", {"platform": "tiktok"})


def test_reads_analytics_platform_availability_and_details():
    http = FakeHTTP()
    analytics = Analytics(http)

    platforms = analytics.platforms(from_date="2026-05-01", to_date="2026-05-31")
    platform = analytics.platform("tiktok", profile_id="prof_1")

    assert platforms[0]["platform"] == "tiktok"
    assert platform["summary"]["posts"] == 3
    assert http.calls[0] == (
        "GET",
        "/v1/analytics/platforms",
        {"from": "2026-05-01", "to": "2026-05-31"},
    )
    assert http.calls[1] == (
        "GET",
        "/v1/analytics/platforms/tiktok",
        {"profile_id": "prof_1"},
    )


def test_requests_analytics_refresh():
    http = FakeHTTP()
    analytics = Analytics(http)

    result = analytics.refresh(platform="threads", limit=5)

    assert result["status"] == "queued"
    assert result["requested_count"] == 5
    assert http.calls[0] == (
        "POST",
        "/v1/analytics/refresh",
        {"platform": "threads", "limit": 5},
        None,
    )
