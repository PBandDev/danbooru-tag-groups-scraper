import asyncio

import httpx


def test_default_headers_include_scraper_user_agent() -> None:
    from danbooru_tag_groups.fetch import default_headers

    headers = default_headers()

    assert headers["User-Agent"].startswith("danbooru-tag-groups-scraper/")
    assert headers["Accept"].startswith("application/json")


def test_fetch_json_retries_once_after_rate_limit(monkeypatch) -> None:
    from danbooru_tag_groups import fetch

    attempts = {"count": 0}
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    async def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "1"}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(fetch.asyncio, "sleep", fake_sleep)

    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch.fetch_json(client, "https://example.test/wiki.json")

    data = asyncio.run(run())

    assert data == {"ok": True}
    assert attempts["count"] == 2
    assert delays == [1.0]
