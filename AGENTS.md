# Danbooru tag-group scraper using `uv` and Danbooru's `wiki_pages` API.

Uses `uv` for dependency management and execution.

Key commands:
- `uv sync --extra dev`
- `uv run pytest -q`
- `uv run python -m danbooru_tag_groups.cli scrape --output-dir ./data`
