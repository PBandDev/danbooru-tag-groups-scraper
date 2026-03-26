import json


def test_cli_scrape_writes_outputs(tmp_path, monkeypatch) -> None:
    from danbooru_tag_groups.cli import main
    from danbooru_tag_groups.models import Page, Section, TagEntry

    async def fake_scrape_site(*, root_url: str, timeout: float, delay_ms: int, max_pages, verbose: bool):
        assert root_url == "https://danbooru.donmai.us/wiki_pages/tag_groups"
        assert timeout == 20.0
        assert delay_ms == 250
        assert max_pages is None
        assert verbose is False
        return [
            Page(
                title="Attire",
                kind="tag_group",
                slug="tag_group:attire",
                url="https://danbooru.donmai.us/wiki_pages/tag_group%3Aattire",
                sections=[
                    Section(
                        title="Headwear and Headgear",
                        path=["Attire", "Headwear and Headgear"],
                        tags=[
                            TagEntry(
                                label="hair bow",
                                canonical_name="hair_bow",
                                url="https://danbooru.donmai.us/wiki_pages/hair_bow",
                                notes=None,
                            )
                        ],
                        children=[],
                    )
                ],
            )
        ]

    async def fake_expand_pages_with_implications(*, pages, timeout: float, delay_ms: int):
        assert timeout == 20.0
        assert delay_ms == 250
        return pages

    monkeypatch.setattr("danbooru_tag_groups.cli.scrape_site", fake_scrape_site)
    monkeypatch.setattr("danbooru_tag_groups.cli.expand_pages_with_implications", fake_expand_pages_with_implications)

    exit_code = main(["scrape", "--output-dir", str(tmp_path)])

    hierarchical = json.loads((tmp_path / "tag_groups_hierarchical.json").read_text(encoding="utf-8"))
    flat_rows = (tmp_path / "tag_groups_flat.jsonl").read_text(encoding="utf-8").splitlines()

    assert exit_code == 0
    assert hierarchical["pages"][0]["slug"] == "tag_group:attire"
    assert len(flat_rows) == 1


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
                        tags=[
                            TagEntry(
                                label="skirt",
                                canonical_name="skirt",
                                url="https://danbooru.donmai.us/wiki_pages/skirt",
                            )
                        ],
                        children=[],
                    )
                ],
            )
        ]

    async def fake_expand_pages_with_implications(*, pages, timeout: float, delay_ms: int):
        assert timeout == 20.0
        assert delay_ms == 250
        pages[0].sections[0].tags.append(
            TagEntry(
                label="red skirt",
                canonical_name="red_skirt",
                url="https://danbooru.donmai.us/wiki_pages/red_skirt",
                source="implication",
                implied_via="skirt",
            )
        )
        return pages

    monkeypatch.setattr("danbooru_tag_groups.cli.scrape_site", fake_scrape_site)
    monkeypatch.setattr("danbooru_tag_groups.cli.expand_pages_with_implications", fake_expand_pages_with_implications)

    exit_code = main(["scrape", "--output-dir", str(tmp_path)])

    flat_rows = [json.loads(line) for line in (tmp_path / "tag_groups_flat.jsonl").read_text(encoding="utf-8").splitlines()]

    assert exit_code == 0
    assert flat_rows[-1]["canonical_name"] == "red_skirt"
    assert flat_rows[-1]["source"] == "implication"

