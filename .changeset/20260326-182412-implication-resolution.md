---
"danbooru-tag-groups-scraper": patch
---

## Description of change

Problem: the scraper only exported tags listed directly on Danbooru tag-group wiki pages, so implied variant tags were missing from the dataset and leaked past downstream filters.

Solution: fetch active `tag_implications`, propagate group membership transitively from direct wiki tags to implied child tags, and export provenance fields so downstream consumers can distinguish direct rows from inherited rows.

## Files modified

- `README.md`
- `src/danbooru_tag_groups/cli.py`
- `src/danbooru_tag_groups/export.py`
- `src/danbooru_tag_groups/fetch.py`
- `src/danbooru_tag_groups/implications.py`
- `src/danbooru_tag_groups/models.py`
- `tests/test_cli.py`
- `tests/test_export.py`
- `tests/test_fetch.py`
- `tests/test_implications.py`
- `tests/test_public_release_contract.py`

## Remaining issues or follow-up

- The resolver currently uses Danbooru implication edges as returned and assumes duplicate section assignments should accumulate; if downstream consumers want deduplicated cross-section behavior, decide that policy explicitly.
- The live smoke test covers the end-to-end path, but there is not yet a focused live assertion for a known implication pair such as `red_skirt -> skirt`.

## Followup prompt

`Add a focused live assertion for a stable implication example and consider whether implication fetch caching is worth the added complexity.`

## Manual tests

- `uv run python -m pytest -q`
- `uv run python -m pytest -q --live tests/test_live.py -v`
- `uv run python -m danbooru_tag_groups.cli scrape --output-dir .tmp-manual --max-pages 2 --delay-ms 0`
- Verified `.tmp-manual/tag_groups_flat.jsonl` contained implication-derived rows with `source` and `implied_via`

## Git commit message

`feat: resolve tag implications in exported dataset`
