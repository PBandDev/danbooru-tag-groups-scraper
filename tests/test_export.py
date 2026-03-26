import json


def test_export_writes_hierarchical_and_flat_outputs(tmp_path) -> None:
    from danbooru_tag_groups.export import export_outputs
    from danbooru_tag_groups.models import Page, Section, TagEntry

    page = Page(
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

    hierarchical_path, flat_path = export_outputs(
        pages=[page],
        output_dir=tmp_path,
        root_url="https://danbooru.donmai.us/wiki_pages/tag_groups",
    )

    hierarchical = json.loads(hierarchical_path.read_text(encoding="utf-8"))
    flat_rows = [json.loads(line) for line in flat_path.read_text(encoding="utf-8").splitlines()]

    assert hierarchical["source"]["root_url"] == "https://danbooru.donmai.us/wiki_pages/tag_groups"
    assert hierarchical["source"]["pages_scraped"] == 1
    assert hierarchical["pages"][0]["title"] == "Attire"
    assert flat_rows == [
        {
            "page_title": "Attire",
            "page_kind": "tag_group",
            "page_slug": "tag_group:attire",
            "page_url": "https://danbooru.donmai.us/wiki_pages/tag_group%3Aattire",
            "section_title": "Headwear and Headgear",
            "section_path": ["Attire", "Headwear and Headgear"],
            "tag_label": "hair bow",
            "canonical_name": "hair_bow",
            "tag_url": "https://danbooru.donmai.us/wiki_pages/hair_bow",
            "notes": None,
            "source": "wiki",
        }
    ]


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

