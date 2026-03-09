from __future__ import annotations

import asyncio
from urllib.parse import quote

import httpx

from danbooru_tag_groups.models import Page
from danbooru_tag_groups.parse import parse_index_body, parse_wiki_page_record


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_FETCH_ATTEMPTS = 5


def default_headers() -> dict[str, str]:
    return {
        "User-Agent": "danbooru-tag-groups-scraper/0.1 (+local-cli)",
        "Accept": "application/json,text/html,application/xhtml+xml",
    }


def wiki_page_json_url(title: str) -> str:
    return f"https://danbooru.donmai.us/wiki_pages/{quote(title, safe='')}.json"


async def fetch_json(client: httpx.AsyncClient, url: str) -> dict[str, object]:
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        response = await client.get(url)
        if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_FETCH_ATTEMPTS:
            await asyncio.sleep(_retry_delay_seconds(response, attempt))
            continue

        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f"Expected object response from {url}")
        return data

    raise RuntimeError(f"Exhausted fetch attempts for {url}")


async def scrape_site(
    *,
    root_url: str,
    timeout: float,
    delay_ms: int,
    max_pages: int | None,
    verbose: bool,
) -> list[Page]:
    del verbose
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=default_headers()) as client:
        root_title = root_url.rstrip("/").rsplit("/", 1)[-1]
        root_record = await fetch_json(client, wiki_page_json_url(root_title))
        root_body = root_record.get("body")
        if not isinstance(root_body, str):
            raise ValueError("Root wiki page record is missing a string body")

        page_refs = parse_index_body(root_body)
        if max_pages is not None:
            page_refs = page_refs[:max_pages]

        pages: list[Page] = []
        for index, page_ref in enumerate(page_refs):
            page_record = await fetch_json(client, wiki_page_json_url(page_ref.slug))
            pages.append(parse_wiki_page_record(page_record))
            if delay_ms > 0 and index < len(page_refs) - 1:
                await asyncio.sleep(delay_ms / 1000)

        return pages


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            pass
    return float(min(2 ** (attempt - 1), 30))
