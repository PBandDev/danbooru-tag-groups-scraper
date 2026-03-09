import pytest


@pytest.mark.live
def test_live_scrape_smoke_requires_live_flag(tmp_path) -> None:
    from danbooru_tag_groups.cli import main

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

    assert exit_code == 0
    assert (tmp_path / "tag_groups_hierarchical.json").exists()
    assert (tmp_path / "tag_groups_flat.jsonl").exists()
