# Danbooru tag groups scraper

## Release

Latest dataset releases live on the [GitHub releases page](https://github.com/PBandDev/danbooru-tag-groups-scraper/releases).

The monthly release job publishes these files:

- `tag_groups_hierarchical.json`
- `tag_groups_flat.jsonl`

Same-month reruns refresh that month's release assets if the publish job needs to be run again.

## What this repo does

This project reads Danbooru's `tag_groups` wiki index through the `wiki_pages` API, follows linked `tag_group:*` and `list_of_*` pages, and exports the results in two formats:

- `tag_groups_hierarchical.json`: nested pages, sections, and tags
- `tag_groups_flat.jsonl`: one tag row per line, which is easier to load into scripts and data tools

## Quick start

Requirements:

- Python 3.12+
- `uv`

Install dependencies and run a scrape:

```bash
git clone https://github.com/PBandDev/danbooru-tag-groups-scraper.git
cd danbooru-tag-groups-scraper
uv sync --extra dev
uv run python -m danbooru_tag_groups.cli scrape --output-dir ./data
```

You can also use the installed CLI entrypoint:

```bash
uv run danbooru-tag-groups scrape --output-dir ./data
```

## Common commands

Run the scraper:

```bash
uv run python -m danbooru_tag_groups.cli scrape --output-dir ./data
```

Run the offline test suite:

```bash
uv run python -m pytest -q
```

Run the live smoke test against Danbooru:

```bash
uv run python -m pytest -q --live tests/test_live.py -v
```

Useful scraper flags:

- `--root-url`: start from a different wiki page
- `--output-dir`: choose where the export files should go
- `--timeout`: request timeout in seconds, default `20`
- `--delay-ms`: wait between page requests, default `250`
- `--max-pages`: limit the number of pages for smoke runs
- `--verbose`: reserved for extra CLI output

Default source page:

- `https://danbooru.donmai.us/wiki_pages/tag_groups`

The default test run stays offline. Only tests marked with `--live` hit Danbooru directly.
