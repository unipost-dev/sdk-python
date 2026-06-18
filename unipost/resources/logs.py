"""Developer logs resource."""

from __future__ import annotations

import json
from typing import Any, Generator, Iterable, Optional, Union


def _query(
    *,
    category: Optional[str] = None,
    action: Optional[str] = None,
    source: Optional[str] = None,
    level: Optional[str] = None,
    status: Optional[str] = None,
    platform: Optional[str] = None,
    profile_id: Optional[str] = None,
    social_account_id: Optional[str] = None,
    post_id: Optional[str] = None,
    request_id: Optional[str] = None,
    error_code: Optional[str] = None,
    q: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    after_id: Optional[int] = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if category:
        query["category"] = category
    if action:
        query["action"] = action
    if source:
        query["source"] = source
    if level:
        query["level"] = level
    if status:
        query["status"] = status
    if platform:
        query["platform"] = platform
    if profile_id:
        query["profile_id"] = profile_id
    if social_account_id:
        query["social_account_id"] = social_account_id
    if post_id:
        query["post_id"] = post_id
    if request_id:
        query["request_id"] = request_id
    if error_code:
        query["error_code"] = error_code
    if q:
        query["q"] = q
    if from_date:
        query["from"] = from_date
    if to_date:
        query["to"] = to_date
    if limit is not None:
        query["limit"] = limit
    if cursor:
        query["cursor"] = cursor
    if after_id is not None:
        query["after_id"] = after_id
    return query


def _parse_sse_lines(lines: Iterable[str]) -> Generator[dict[str, Any], None, None]:
    event_name: Optional[str] = None
    data_lines: list[str] = []

    def flush() -> Optional[dict[str, Any]]:
        nonlocal event_name, data_lines
        if not data_lines:
            event_name = None
            return None
        raw = "\n".join(data_lines)
        event = event_name
        event_name = None
        data_lines = []
        if event and event != "log.created":
            return None
        return json.loads(raw)

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if line == "":
            item = flush()
            if item is not None:
                yield item
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)

    item = flush()
    if item is not None:
        yield item


class Logs:
    def __init__(self, http: Any) -> None:
        self._http = http

    def list(
        self,
        *,
        category: Optional[str] = None,
        action: Optional[str] = None,
        source: Optional[str] = None,
        level: Optional[str] = None,
        status: Optional[str] = None,
        platform: Optional[str] = None,
        profile_id: Optional[str] = None,
        social_account_id: Optional[str] = None,
        post_id: Optional[str] = None,
        request_id: Optional[str] = None,
        error_code: Optional[str] = None,
        q: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        resp = self._http.get(
            "/v1/logs",
            query=_query(
                category=category,
                action=action,
                source=source,
                level=level,
                status=status,
                platform=platform,
                profile_id=profile_id,
                social_account_id=social_account_id,
                post_id=post_id,
                request_id=request_id,
                error_code=error_code,
                q=q,
                from_date=from_date,
                to_date=to_date,
                limit=limit,
                cursor=cursor,
            )
            or None,
        )
        meta = resp.get("meta") or {}
        resp["next_cursor"] = meta.get("next_cursor") or resp.get("next_cursor")
        return resp

    def get(self, log_id: int | str) -> dict[str, Any]:
        resp = self._http.get(f"/v1/logs/{log_id}")
        return resp["data"]

    def stream(
        self,
        *,
        category: Optional[str] = None,
        level: Optional[str] = None,
        status: Optional[str] = None,
        platform: Optional[str] = None,
        profile_id: Optional[str] = None,
        social_account_id: Optional[str] = None,
        post_id: Optional[str] = None,
        request_id: Optional[str] = None,
        error_code: Optional[str] = None,
        after_id: Optional[int] = None,
        last_event_id: Optional[Union[int, str]] = None,
    ) -> Generator[dict[str, Any], None, None]:
        headers = {"Accept": "text/event-stream"}
        if last_event_id is not None:
            headers["Last-Event-ID"] = str(last_event_id)
        return _parse_sse_lines(
            self._http.stream(
                "/v1/logs/stream",
                query=_query(
                    category=category,
                    level=level,
                    status=status,
                    platform=platform,
                    profile_id=profile_id,
                    social_account_id=social_account_id,
                    post_id=post_id,
                    request_id=request_id,
                    error_code=error_code,
                    after_id=after_id,
                )
                or None,
                headers=headers,
            )
        )
