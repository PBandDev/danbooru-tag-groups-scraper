from pathlib import Path

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_index_page_filters_to_supported_wiki_targets() -> None:
    from danbooru_tag_groups.parse import parse_index_page

    page_refs = parse_index_page(
        read_fixture("index.html"),
        root_url="https://danbooru.donmai.us/wiki_pages/tag_groups",
    )

    assert [page_ref.slug for page_ref in page_refs] == [
        "tag_group:attire",
        "list_of_style_parodies",
        "tag_group:artistic_license",
    ]
    assert [page_ref.kind for page_ref in page_refs] == [
        "tag_group",
        "list",
        "tag_group",
    ]


def test_parse_group_page_builds_nested_sections_and_preserves_notes() -> None:
    from danbooru_tag_groups.parse import parse_group_page

    page = parse_group_page(
        read_fixture("attire.html"),
        url="https://danbooru.donmai.us/wiki_pages/tag_group%3Aattire",
    )

    assert page.title == "Attire"
    assert page.kind == "tag_group"
    assert page.slug == "tag_group:attire"
    assert [section.title for section in page.sections] == [
        "Headwear and Headgear",
        "Jewelry and Accessories",
    ]

    headwear = page.sections[0]
    assert [tag.canonical_name for tag in headwear.tags] == [
        "hair_bow",
        "trench_coat",
        "veil",
    ]
    assert headwear.tags[1].notes == "outerwear"

    jewelry = page.sections[1]
    assert [child.title for child in jewelry.children] == ["Head and Face", "Not headwear"]
    assert [tag.canonical_name for tag in jewelry.children[0].tags] == [
        "monocle",
        "hair_ornament",
    ]


def test_parse_group_page_uses_url_slug_for_canonical_names_when_available() -> None:
    from danbooru_tag_groups.parse import parse_group_page

    page = parse_group_page(
        read_fixture("style_parodies.html"),
        url="https://danbooru.donmai.us/wiki_pages/list_of_style_parodies",
    )

    by_copyright_rows = page.sections[0].children[0].tags
    artist_style_rows = page.sections[0].children[1].tags
    assert [tag.canonical_name for tag in by_copyright_rows] == [
        "friday_night_funkin'_(style)",
    ]
    assert [tag.canonical_name for tag in artist_style_rows] == [
        "studio_ghibli_(style)",
        "miyazaki_hayao_(style)",
        "william-adolphe_bouguereau_(style)",
    ]
    assert artist_style_rows[-1].notes == "Academic art"


def test_parse_group_page_deduplicates_tags_within_same_section_only() -> None:
    from danbooru_tag_groups.export import build_flat_rows
    from danbooru_tag_groups.parse import parse_group_page

    page = parse_group_page(
        read_fixture("attire.html"),
        url="https://danbooru.donmai.us/wiki_pages/tag_group%3Aattire",
    )

    flat_rows = build_flat_rows([page])
    trench_rows = [row for row in flat_rows if row["canonical_name"] == "trench_coat"]
    veil_rows = [row for row in flat_rows if row["canonical_name"] == "veil"]

    assert len(trench_rows) == 1
    assert len(veil_rows) == 2
    assert trench_rows[0]["section_path"] == ["Attire", "Headwear and Headgear"]


def test_parse_group_page_rejects_pages_without_heading() -> None:
    from danbooru_tag_groups.parse import parse_group_page

    with pytest.raises(ValueError, match="page title"):
        parse_group_page("<html><body><p>No heading</p></body></html>", url="https://example.com")


def test_parse_group_page_falls_back_to_document_heading_outside_wiki_body() -> None:
    from danbooru_tag_groups.parse import parse_group_page

    page = parse_group_page(
        read_fixture("document_title_outside_body.html"),
        url="https://danbooru.donmai.us/wiki_pages/tag_group%3Aartistic_license",
    )

    assert page.title == "Artistic License"
    assert [section.title for section in page.sections] == ["Major changes"]


def test_parse_group_page_prefers_document_h1_over_earlier_site_chrome_h2() -> None:
    from danbooru_tag_groups.parse import parse_group_page

    page = parse_group_page(
        read_fixture("document_title_prefers_h1.html"),
        url="https://danbooru.donmai.us/wiki_pages/tag_group%3Aartistic_license",
    )

    assert page.title == "Artistic License"
