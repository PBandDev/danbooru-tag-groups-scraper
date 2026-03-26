from __future__ import annotations

from collections import deque
import asyncio

import httpx

from danbooru_tag_groups.fetch import default_headers, fetch_json_list
from danbooru_tag_groups.models import Page, Section, TagEntry


TAG_IMPLICATIONS_URL = "https://danbooru.donmai.us/tag_implications.json"


async def expand_pages_with_implications(*, pages: list[Page], timeout: float, delay_ms: int) -> list[Page]:
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=default_headers(),
    ) as client:
        implications = await fetch_all_tag_implications(client, delay_ms=delay_ms)
    return apply_implied_tags(pages=pages, implications=implications)


async def fetch_all_tag_implications(client: httpx.AsyncClient, *, delay_ms: int) -> list[dict[str, object]]:
    page = 1
    implications: list[dict[str, object]] = []

    while True:
        page_rows = await fetch_json_list(
            client,
            TAG_IMPLICATIONS_URL,
            params={"page": page, "limit": 1000, "search[status]": "active"},
        )
        if not page_rows:
            return implications

        implications.extend(page_rows)
        page += 1
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)


def apply_implied_tags(*, pages: list[Page], implications: list[dict[str, object]]) -> list[Page]:
    expanded_pages = [_clone_page(page) for page in pages]
    sections_by_key = {
        (page.slug, tuple(section.path)): section
        for page in expanded_pages
        for section in _iter_sections(page.sections)
    }

    for row in resolve_implied_tags(pages=pages, implications=implications):
        if row["source"] != "implication":
            continue

        section = sections_by_key[(row["page_slug"], tuple(row["section_path"]))]
        section.tags.append(
            TagEntry(
                label=row["tag_label"],
                canonical_name=row["canonical_name"],
                url=row["tag_url"],
                notes=row["notes"],
                source=row["source"],
                implied_via=row["implied_via"],
            )
        )

    return expanded_pages


def resolve_implied_tags(
    *, pages: list[Page], implications: list[dict[str, object]]
) -> list[dict[str, object]]:
    rows = _build_direct_rows(pages)
    rows_by_tag: dict[str, list[dict[str, object]]] = {}
    seen: set[tuple[str, str, tuple[str, ...]]] = set()

    for row in rows:
        rows_by_tag.setdefault(row["canonical_name"], []).append(row)
        seen.add((row["canonical_name"], row["page_slug"], tuple(row["section_path"])))

    children_by_parent: dict[str, list[str]] = {}
    for implication in implications:
        status = implication.get("status")
        antecedent = implication.get("antecedent_name")
        consequent = implication.get("consequent_name")
        if status != "active" or not isinstance(antecedent, str) or not isinstance(consequent, str):
            continue
        children_by_parent.setdefault(consequent, []).append(antecedent)

    queue: deque[str] = deque(rows_by_tag)
    inherited_rows: list[dict[str, object]] = []

    while queue:
        parent = queue.popleft()
        parent_rows = rows_by_tag.get(parent, [])
        for child in children_by_parent.get(parent, []):
            for parent_row in parent_rows:
                row_key = (child, parent_row["page_slug"], tuple(parent_row["section_path"]))
                if row_key in seen:
                    continue

                child_row = {
                    **parent_row,
                    "tag_label": child.replace("_", " "),
                    "canonical_name": child,
                    "tag_url": f"https://danbooru.donmai.us/wiki_pages/{child}",
                    "source": "implication",
                    "implied_via": parent,
                }
                inherited_rows.append(child_row)
                rows_by_tag.setdefault(child, []).append(child_row)
                queue.append(child)
                seen.add(row_key)

    return rows + inherited_rows


def _build_direct_rows(pages: list[Page]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for page in pages:
        for section in page.sections:
            rows.extend(_section_rows(page, section))
    return rows


def _section_rows(page: Page, section: Section) -> list[dict[str, object]]:
    rows = [
        {
            "page_title": page.title,
            "page_kind": page.kind,
            "page_slug": page.slug,
            "page_url": page.url,
            "section_title": section.title,
            "section_path": section.path,
            "tag_label": tag.label,
            "canonical_name": tag.canonical_name,
            "tag_url": tag.url,
            "notes": tag.notes,
            "source": "wiki",
        }
        for tag in section.tags
    ]
    for child in section.children:
        rows.extend(_section_rows(page, child))
    return rows


def _clone_page(page: Page) -> Page:
    return Page(
        title=page.title,
        kind=page.kind,
        slug=page.slug,
        url=page.url,
        sections=[_clone_section(section) for section in page.sections],
    )


def _clone_section(section: Section) -> Section:
    return Section(
        title=section.title,
        path=[*section.path],
        tags=[
            TagEntry(
                label=tag.label,
                canonical_name=tag.canonical_name,
                url=tag.url,
                notes=tag.notes,
                source=tag.source,
                implied_via=tag.implied_via,
            )
            for tag in section.tags
        ],
        children=[_clone_section(child) for child in section.children],
    )


def _iter_sections(sections: list[Section]) -> list[Section]:
    all_sections: list[Section] = []
    for section in sections:
        all_sections.append(section)
        all_sections.extend(_iter_sections(section.children))
    return all_sections
