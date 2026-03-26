---
"danbooru-tag-groups-scraper": patch
---

## Description of change

Problem: the monthly release recreation workflow could delete the existing release and then fail on a transient GitHub Releases API error during `gh release create`, leaving the month with no release.

Solution: add bounded retries around monthly release creation so transient GitHub API failures do not strand the release after deletion.

## Files modified

- `.github/workflows/publish-data.yml`
- `tests/test_public_release_contract.py`

## Remaining issues or follow-up

- The workflow still performs delete-then-create, so a long GitHub outage could still leave the release absent until the next rerun.
- If this keeps happening, the next step would be a more defensive staged-tag strategy instead of direct recreation.

## Followup prompt

`Evaluate whether the monthly release workflow should switch to a staged tag flow to avoid delete-then-create gaps during GitHub API incidents.`

## Manual tests

- `uv run python -m pytest -q tests/test_public_release_contract.py::test_publish_workflow_uses_versioned_monthly_releases -v`
- `uv run python -m pytest -q`
- Triggered `Publish Data` on GitHub after push to verify release recreation succeeds end-to-end

## Git commit message

`fix: retry monthly release creation`
