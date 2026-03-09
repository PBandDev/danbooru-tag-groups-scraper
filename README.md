# Danbooru Tag Groups Scraper

Scrapes Danbooru's `tag_groups` wiki index through the `wiki_pages` API, follows linked `tag_group:*` and `list_of_*` pages, and writes two dataset exports:

- `tag_groups_hierarchical.json`
- `tag_groups_flat.jsonl`

## Requirements

- Python 3.12+
- `uv`

## Quickstart

```bash
git clone <your-repo-url>
cd danbooru-tag-groups-scraper
uv sync --extra dev
uv run python -m danbooru_tag_groups.cli scrape --output-dir ./data
```

## Usage

```bash
uv run python -m danbooru_tag_groups.cli scrape --output-dir ./data
```

Useful flags:

- `--root-url`: override the starting wiki page
- `--delay-ms`: throttle between page fetches, defaults to `250`
- `--timeout`: request timeout in seconds, defaults to `20`
- `--max-pages`: limit page count for smoke runs

Default source:

- `https://danbooru.donmai.us/wiki_pages/tag_groups`

## Testing

```bash
uv run python -m pytest -q
```

Live smoke test against Danbooru:

```bash
uv run python -m pytest -q --live tests/test_live.py -v
```

The default test command stays offline. The `--live` run hits Danbooru directly.

## Releases

The repo includes GitHub Actions for:

- CI on pushes and pull requests to `main`
- monthly GitHub releases published from `main`

Each monthly release uploads the current `tag_groups_hierarchical.json` and `tag_groups_flat.jsonl` files as release assets. Same-month reruns refresh that month's release assets for recovery.
