---
"danbooru-tag-groups-scraper": patch
---

## Description of change

Problem: rerunning the monthly publish workflow edited the existing GitHub release in place, so GitHub still showed the original publish date and it looked like no new release had appeared.

Solution: change the workflow to delete and recreate the same monthly release tag on reruns, preserving the monthly release scheme while surfacing a fresh release timestamp in the GitHub UI.

## Files modified

- `.github/workflows/publish-data.yml`
- `README.md`
- `tests/test_public_release_contract.py`

## Remaining issues or follow-up

- Existing monthly releases created before this change will still show their original publish dates until a rerun recreates them.
- If preserving release comments or manual edits ever matters, this workflow will intentionally replace them on rerun.

## Followup prompt

`Add a small troubleshooting section to the README that explains where monthly reruns appear in the GitHub Releases UI.`

## Manual tests

- `uv run python -m pytest -q tests/test_public_release_contract.py::test_publish_workflow_uses_versioned_monthly_releases tests/test_public_release_contract.py::test_readme_documents_offline_and_live_test_commands -v`
- `uv run python -m pytest -q`

## Git commit message

`fix: recreate monthly release on rerun`
