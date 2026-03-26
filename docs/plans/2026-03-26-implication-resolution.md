# Tag Implication Resolution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand the exported tag-group dataset with Danbooru `tag_implications` so variant tags inherit the same group membership as their implied base tags.

**Architecture:** Keep the existing wiki-page scrape as the source of truth for direct group membership, then add a second pass that fetches active implications, computes inherited memberships transitively, and emits enriched exports. Isolate the new logic in a dedicated implication-resolution module so the fetch, resolution, export, and CLI changes stay testable in small pieces.

**Tech Stack:** Python 3.12, `httpx`, `argparse`, `pytest`, `uv`

---

### Task 1: Add implication-resolution domain model

**Files:**
- Create: `src/danbooru_tag_groups/implications.py`
- Modify: `src/danbooru_tag_groups/models.py`
- Test: `tests/test_implications.py`

**Step 1: Write the failing test**

```python
from danbooru_tag_groups.implications import resolve_implied_tags
from danbooru_tag_groups.models import Page, Section, TagEntry


def test_resolve_implied_tags_propagates_groups_transitively() -> None:
    pages = [
        Page(
            title="Attire",
            kind="tag_group",
            slug="tag_group:attire",
            url="https://danbooru.donmai.us/wiki_pages/tag_group%3Aattire",
            sections=[
                Section(
                    title="Bottoms",
                    path=["Attire", "Bottoms"],
                    tags=[
                        TagEntry(
                            label="skirt",
                            canonical_name="skirt",
                            url="https://danbooru.donmai.us/wiki_pages/skirt",
                            notes=None,
                        )
                    ],
                    children=[],
                )
            ],
        )
    ]

    rows = resolve_implied_tags(
        pages=pages,
        implications=[
            {"antecedent_name": "red_skirt", "consequent_name": "skirt", "status": "active"},
            {"antecedent_name": "dark_red_skirt", "consequent_name": "red_skirt", "status": "active"},
        ],
    )

    assert ("red_skirt", "skirt", "implication") in {
        (row["canonical_name"], row.get("implied_via"), row["source"]) for row in rows
    }
    assert ("dark_red_skirt", "red_skirt", "implication") in {
        (row["canonical_name"], row.get("implied_via"), row["source"]) for row in rows
    }
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest -q tests/test_implications.py::test_resolve_implied_tags_propagates_groups_transitively -v`
Expected: FAIL with `ModuleNotFoundError` or missing `resolve_implied_tags`

**Step 3: Write minimal implementation**

```python
from collections import deque


def resolve_implied_tags(*, pages, implications):
    seed_rows = _build_direct_rows(pages)
    grouped_rows = _index_rows_by_tag(seed_rows)
    queue = deque(grouped_rows)
    seen_pairs = {(row["canonical_name"], row["page_slug"], tuple(row["section_path"])) for row in seed_rows}
    inherited = []

    children_by_parent = {}
    for item in implications:
        if item.get("status") != "active":
            continue
        children_by_parent.setdefault(item["consequent_name"], []).append(item["antecedent_name"])

    while queue:
        parent = queue.popleft()
        for child in children_by_parent.get(parent, []):
            for row in grouped_rows[parent]:
                key = (child, row["page_slug"], tuple(row["section_path"]))
                if key in seen_pairs:
                    continue
                new_row = {
                    **row,
                    "canonical_name": child,
                    "tag_label": child.replace("_", " "),
                    "tag_url": f"https://danbooru.donmai.us/wiki_pages/{child}",
                    "source": "implication",
                    "implied_via": parent,
                }
                inherited.append(new_row)
                grouped_rows.setdefault(child, []).append(new_row)
                queue.append(child)
                seen_pairs.add(key)

    return seed_rows + inherited
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest -q tests/test_implications.py::test_resolve_implied_tags_propagates_groups_transitively -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_implications.py src/danbooru_tag_groups/models.py src/danbooru_tag_groups/implications.py
git commit -m "feat: add implication resolution primitives"
```

### Task 2: Add paginated implication fetcher with retry behavior

**Files:**
- Modify: `src/danbooru_tag_groups/fetch.py`
- Modify: `src/danbooru_tag_groups/implications.py`
- Test: `tests/test_fetch.py`

**Step 1: Write the failing test**

```python
import asyncio
import httpx


def test_fetch_all_tag_implications_paginates_until_empty(monkeypatch) -> None:
    from danbooru_tag_groups.implications import fetch_all_tag_implications

    responses = {
        1: [{"antecedent_name": "red_skirt", "consequent_name": "skirt", "status": "active"}],
        2: [{"antecedent_name": "yellow_ascot", "consequent_name": "ascot", "status": "active"}],
        3: [],
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        return httpx.Response(200, json=responses[page], request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_all_tag_implications(client, delay_ms=0)

    data = asyncio.run(run())

    assert [item["antecedent_name"] for item in data] == ["red_skirt", "yellow_ascot"]
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest -q tests/test_fetch.py::test_fetch_all_tag_implications_paginates_until_empty -v`
Expected: FAIL because `fetch_all_tag_implications` does not exist

**Step 3: Write minimal implementation**

```python
TAG_IMPLICATIONS_URL = "https://danbooru.donmai.us/tag_implications.json"


async def fetch_all_tag_implications(client: httpx.AsyncClient, *, delay_ms: int) -> list[dict[str, object]]:
    page = 1
    all_rows: list[dict[str, object]] = []

    while True:
        response = await client.get(
            TAG_IMPLICATIONS_URL,
            params={"page": page, "limit": 1000, "search[status]": "active"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Expected implication API to return a list")
        if not payload:
            return all_rows
        all_rows.extend(item for item in payload if isinstance(item, dict))
        page += 1
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest -q tests/test_fetch.py::test_fetch_all_tag_implications_paginates_until_empty -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_fetch.py src/danbooru_tag_groups/fetch.py src/danbooru_tag_groups/implications.py
git commit -m "feat: fetch active tag implications"
```

### Task 3: Enrich exports with provenance metadata

**Files:**
- Modify: `src/danbooru_tag_groups/models.py`
- Modify: `src/danbooru_tag_groups/export.py`
- Modify: `tests/test_export.py`
- Test: `tests/test_implications.py`

**Step 1: Write the failing test**

```python
def test_build_flat_rows_marks_direct_and_inherited_sources() -> None:
    from danbooru_tag_groups.export import build_flat_rows
    from danbooru_tag_groups.models import Page, Section, TagEntry

    page = Page(
        title="Attire",
        kind="tag_group",
        slug="tag_group:attire",
        url="https://danbooru.donmai.us/wiki_pages/tag_group%3Aattire",
        sections=[
            Section(
                title="Bottoms",
                path=["Attire", "Bottoms"],
                tags=[
                    TagEntry(
                        label="skirt",
                        canonical_name="skirt",
                        url="https://danbooru.donmai.us/wiki_pages/skirt",
                        source="wiki",
                    ),
                    TagEntry(
                        label="red skirt",
                        canonical_name="red_skirt",
                        url="https://danbooru.donmai.us/wiki_pages/red_skirt",
                        source="implication",
                        implied_via="skirt",
                    ),
                ],
                children=[],
            )
        ],
    )

    rows = build_flat_rows([page])

    assert rows[0]["source"] == "wiki"
    assert "implied_via" not in rows[0]
    assert rows[1]["source"] == "implication"
    assert rows[1]["implied_via"] == "skirt"
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest -q tests/test_export.py::test_build_flat_rows_marks_direct_and_inherited_sources -v`
Expected: FAIL because `TagEntry` and export rows do not carry provenance fields

**Step 3: Write minimal implementation**

```python
@dataclass(slots=True)
class TagEntry:
    label: str
    canonical_name: str
    url: str | None
    notes: str | None = None
    source: str = "wiki"
    implied_via: str | None = None


def _row_from_tag(page: Page, section: Section, tag: TagEntry) -> dict[str, object]:
    row = {
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
        "source": tag.source,
    }
    if tag.implied_via is not None:
        row["implied_via"] = tag.implied_via
    return row
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest -q tests/test_export.py::test_build_flat_rows_marks_direct_and_inherited_sources -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_export.py tests/test_implications.py src/danbooru_tag_groups/models.py src/danbooru_tag_groups/export.py
git commit -m "feat: export implication provenance"
```

### Task 4: Wire implication resolution into the default scrape pipeline

**Files:**
- Modify: `src/danbooru_tag_groups/cli.py`
- Modify: `src/danbooru_tag_groups/export.py`
- Modify: `src/danbooru_tag_groups/implications.py`
- Modify: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
def test_cli_scrape_always_resolves_implications(tmp_path, monkeypatch) -> None:
    from danbooru_tag_groups.cli import main
    from danbooru_tag_groups.models import Page, Section, TagEntry

    async def fake_scrape_site(**kwargs):
        return [
            Page(
                title="Attire",
                kind="tag_group",
                slug="tag_group:attire",
                url="https://danbooru.donmai.us/wiki_pages/tag_group%3Aattire",
                sections=[
                    Section(
                        title="Bottoms",
                        path=["Attire", "Bottoms"],
                        tags=[TagEntry(label="skirt", canonical_name="skirt", url="https://danbooru.donmai.us/wiki_pages/skirt")],
                        children=[],
                    )
                ],
            )
        ]

    async def fake_expand_pages_with_implications(*, pages, timeout, delay_ms):
        assert delay_ms == 250
        return pages

    monkeypatch.setattr("danbooru_tag_groups.cli.scrape_site", fake_scrape_site)
    monkeypatch.setattr("danbooru_tag_groups.cli.expand_pages_with_implications", fake_expand_pages_with_implications)

    exit_code = main(["scrape", "--output-dir", str(tmp_path)])

    assert exit_code == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest -q tests/test_cli.py::test_cli_scrape_always_resolves_implications -v`
Expected: FAIL because the CLI does not invoke implication resolution yet

**Step 3: Write minimal implementation**

```python
pages = asyncio.run(
    scrape_site(
        root_url=args.root_url,
        timeout=args.timeout,
        delay_ms=args.delay_ms,
        max_pages=args.max_pages,
        verbose=args.verbose,
    )
)
pages = asyncio.run(
    expand_pages_with_implications(
        pages=pages,
        timeout=args.timeout,
        delay_ms=args.delay_ms,
    )
)
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest -q tests/test_cli.py::test_cli_scrape_always_resolves_implications -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_cli.py src/danbooru_tag_groups/cli.py src/danbooru_tag_groups/implications.py
git commit -m "feat: resolve implications during scrape"
```

### Task 5: Cover docs, release contract, and live smoke path

**Files:**
- Modify: `README.md`
- Modify: `tests/test_live.py`
- Modify: `tests/test_public_release_contract.py`

**Step 1: Write the failing test**

```python
def test_readme_documents_default_implication_resolution() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert "tag implications" in readme
    assert "variant tags" in readme
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest -q tests/test_public_release_contract.py::test_readme_documents_default_implication_resolution -v`
Expected: FAIL because the README does not mention implication resolution yet

**Step 3: Write minimal implementation**

```markdown
This project reads Danbooru's `tag_groups` wiki index through the `wiki_pages` API, then expands the scraped base tags with active `tag_implications` so variant tags inherit the same group membership in the exported dataset.
```

```python
exit_code = main(
    [
        "scrape",
        "--output-dir",
        str(tmp_path),
        "--max-pages",
        "2",
        "--delay-ms",
        "0",
        "--timeout",
        "20",
    ]
)
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest -q tests/test_public_release_contract.py tests/test_live.py -v`
Expected: PASS offline; live test remains skipped unless `--live` is supplied

**Step 5: Commit**

```bash
git add README.md tests/test_live.py tests/test_public_release_contract.py
git commit -m "docs: document default implication resolution"
```

### Task 6: Run full verification before merge

**Files:**
- Modify: `src/danbooru_tag_groups/implications.py`
- Modify: `src/danbooru_tag_groups/export.py`
- Modify: `src/danbooru_tag_groups/cli.py`
- Modify: `tests/test_implications.py`
- Modify: `tests/test_fetch.py`
- Modify: `tests/test_export.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_live.py`
- Modify: `tests/test_public_release_contract.py`

**Step 1: Run focused offline tests**

Run: `uv run python -m pytest -q tests/test_implications.py tests/test_fetch.py tests/test_export.py tests/test_cli.py tests/test_public_release_contract.py`
Expected: PASS

**Step 2: Run full offline suite**

Run: `uv run python -m pytest -q`
Expected: PASS with the existing live test skipped

**Step 3: Run optional live smoke check**

Run: `uv run python -m pytest -q --live tests/test_live.py -v`
Expected: PASS after fetching a small number of tag-group pages and at least one implication page from Danbooru

**Step 4: Inspect sample output manually**

Run: `uv run python -m danbooru_tag_groups.cli scrape --output-dir ./data --max-pages 2 --delay-ms 0`
Expected: `data/tag_groups_flat.jsonl` contains `source` fields, and implication-derived rows include `implied_via`

**Step 5: Commit**

```bash
git add src/danbooru_tag_groups/implications.py src/danbooru_tag_groups/export.py src/danbooru_tag_groups/cli.py tests/test_implications.py tests/test_fetch.py tests/test_export.py tests/test_cli.py tests/test_live.py tests/test_public_release_contract.py README.md
git commit -m "feat: resolve tag implications in exported dataset"
```
