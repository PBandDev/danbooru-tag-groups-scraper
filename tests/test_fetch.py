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


def test_fetch_all_tag_implications_paginates_until_empty() -> None:
    from danbooru_tag_groups.implications import fetch_all_tag_implications

    responses = {
        1: [{"antecedent_name": "red_skirt", "consequent_name": "skirt", "status": "active"}],
        2: [{"antecedent_name": "yellow_ascot", "consequent_name": "ascot", "status": "active"}],
        3: [],
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        return httpx.Response(200, json=responses[page], request=request)

    async def run() -> list[dict[str, object]]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_all_tag_implications(client, delay_ms=0)

    data = asyncio.run(run())

    assert [item["antecedent_name"] for item in data] == ["red_skirt", "yellow_ascot"]
