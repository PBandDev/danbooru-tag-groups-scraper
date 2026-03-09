from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_wiki_page_json_url_encodes_titles_for_api_requests() -> None:
    from danbooru_tag_groups.fetch import wiki_page_json_url

    assert wiki_page_json_url("tag_groups") == "https://danbooru.donmai.us/wiki_pages/tag_groups.json"
    assert (
        wiki_page_json_url("tag_group:artistic_license")
        == "https://danbooru.donmai.us/wiki_pages/tag_group%3Aartistic_license.json"
    )
    assert (
        wiki_page_json_url("list_of_style_parodies")
        == "https://danbooru.donmai.us/wiki_pages/list_of_style_parodies.json"
    )


def test_parse_index_body_extracts_tag_group_and_list_targets_only() -> None:
    from danbooru_tag_groups.parse import parse_index_body

    page_refs = parse_index_body(read_fixture("index_body.txt"))

    assert [page_ref.slug for page_ref in page_refs] == [
        "tag_group:artistic_license",
        "tag_group:image_composition",
        "tag_group:backgrounds",
        "list_of_style_parodies",
        "tag_group:body_parts",
        "tag_group:ass",
    ]
    assert [page_ref.kind for page_ref in page_refs] == [
        "tag_group",
        "tag_group",
        "tag_group",
        "list",
        "tag_group",
        "tag_group",
    ]


def test_parse_wiki_page_record_parses_api_body_sections_and_tags() -> None:
    from danbooru_tag_groups.parse import parse_wiki_page_record

    page = parse_wiki_page_record(
        {
            "title": "tag_group:artistic_license",
            "body": read_fixture("artistic_license_body.txt"),
        }
    )

    assert page.title == "Artistic License"
    assert page.slug == "tag_group:artistic_license"
    assert [section.title for section in page.sections[:3]] == [
        "Major changes",
        "Changes of the whole attire",
        "Changes of specific clothes or accessories",
    ]
    assert [tag.canonical_name for tag in page.sections[0].tags[:3]] == [
        "alternate_species",
        "animalization",
        "foodification",
    ]
    assert [tag.canonical_name for tag in page.sections[1].tags] == [
        "adapted_costume",
        "alternate_costume",
        "costume_switch",
        "casual",
        "contemporary",
        "enmaided",
        "costume_combination",
        "cosplay",
    ]
    assert page.sections[1].tags[-1].notes is None
    assert [tag.canonical_name for tag in page.sections[2].tags[:3]] == [
        "alternate_headwear",
        "alternate_weapon",
        "bespectacled",
    ]
    assert page.sections[2].tags[2].notes == "added eyewear"


def test_parse_wiki_page_record_handles_empty_alias_targets_and_trailing_notes() -> None:
    from danbooru_tag_groups.parse import parse_wiki_page_record

    page = parse_wiki_page_record(
        {
            "title": "list_of_style_parodies",
            "body": read_fixture("style_parodies_body.txt"),
        }
    )

    assert page.title == "List Of Style Parodies"
    assert [section.title for section in page.sections[:2]] == ["General style parodies", "Artist styles"]
    decade = page.sections[0].children[0]
    assert [tag.label for tag in decade.tags[:3]] == ["retro artstyle", "1920s", "1930s"]
    assert [tag.canonical_name for tag in decade.tags[:3]] == [
        "retro_artstyle",
        "1920s_(style)",
        "1930s_(style)",
    ]
    by_copyright = page.sections[0].children[2]
    assert [tag.canonical_name for tag in by_copyright.tags] == [
        "bikkuriman_(style)",
        "friday_night_funkin'_(style)",
    ]
    artist_a = page.sections[1].children[0]
    assert [tag.canonical_name for tag in artist_a.tags[:3]] == [
        "aaron_mcgruder_(style)",
        "ac-bu_(style)",
        "william-adolphe_bouguereau_(style)",
    ]
    assert artist_a.tags[2].notes == "Academic art"


def test_parse_wiki_page_record_keeps_expand_list_content_but_skips_table_of_contents() -> None:
    from danbooru_tag_groups.parse import parse_wiki_page_record

    page = parse_wiki_page_record(
        {
            "title": "list_of_jojo_no_kimyou_na_bouken_characters",
            "body": """\
This is a list containing all tagged characters and items in [[JoJo no Kimyou na Bouken]].

[expand=Table of Contents]
* 1. "Phantom Blood":#dtext-phantom-blood
[/expand]

h4#phantom-blood. [[Phantom Blood]]

[expand=List]
h5. Allies

* [[Jonathan Joestar]]
* [[Robert E. O. Speedwagon]]

h5. Enemies

* [[Dio Brando]]
[/expand]
""",
        }
    )

    assert [section.title for section in page.sections] == ["Phantom Blood"]
    assert [child.title for child in page.sections[0].children] == ["Allies", "Enemies"]
    assert [tag.canonical_name for tag in page.sections[0].children[0].tags] == [
        "jonathan_joestar",
        "robert_e._o._speedwagon",
    ]
    assert [tag.canonical_name for tag in page.sections[0].children[1].tags] == ["dio_brando"]


def test_parse_wiki_page_record_accepts_h1_through_h6_headings() -> None:
    from danbooru_tag_groups.parse import parse_wiki_page_record

    page = parse_wiki_page_record(
        {
            "title": "list_of_vocal_synth_songs",
            "body": """\
h1. Songs Featuring [[Adachi Rei]]
* [[picdo]]

h3. Songs Featuring [[Chis-A]]
* [[Guzu (Voisona)|]]
""",
        }
    )

    assert [section.title for section in page.sections] == ["Songs Featuring Adachi Rei"]
    assert [tag.canonical_name for tag in page.sections[0].tags] == ["picdo"]
    assert [child.title for child in page.sections[0].children] == ["Songs Featuring Chis-A"]
    assert [tag.canonical_name for tag in page.sections[0].children[0].tags] == ["guzu_(voisona)"]


def test_parse_wiki_page_record_handles_inline_expand_closing_marker() -> None:
    from danbooru_tag_groups.parse import parse_wiki_page_record

    page = parse_wiki_page_record(
        {
            "title": "list_of_arknights_characters",
            "body": """\
[expand=Table of Contents]
* 1. "Rhodes Island":#dtext-rhodes[/expand]

h3. Operators

h5#rhodes. Rhodes Island Pharmaceuticals, inc.
* [[Amiya (arknights)|]]
""",
        }
    )

    assert [section.title for section in page.sections] == ["Operators"]
    assert [child.title for child in page.sections[0].children] == ["Rhodes Island Pharmaceuticals, inc."]
    assert [tag.canonical_name for tag in page.sections[0].children[0].tags] == ["amiya_(arknights)"]


def test_parse_wiki_page_record_captures_top_level_bullets_without_headings() -> None:
    from danbooru_tag_groups.parse import parse_wiki_page_record

    page = parse_wiki_page_record(
        {
            "title": "tag_group:embellishment",
            "body": """\
[See [[Tag Groups]].]

* [[gem-studded]]
* [[glitter]]
* [[lace]]
""",
        }
    )

    assert [section.title for section in page.sections] == ["General"]
    assert [tag.canonical_name for tag in page.sections[0].tags] == ["gem-studded", "glitter", "lace"]


def test_parse_wiki_page_record_extracts_tag_links_from_relevant_table_columns() -> None:
    from danbooru_tag_groups.parse import parse_wiki_page_record

    page = parse_wiki_page_record(
        {
            "title": "list_of_gym_leaders",
            "body": """\
h4. Introduced in the games

[table]
[thead]
[tr]
[th]Game[/th]
[th]Tag[/th]
[th]Children[/th]
[/tr]
[/thead]
[tbody]
[tr]
[td][[pokemon_rgby|RGBY]][/td]
[td][[brock (pokemon)|]][/td]
[td][[Red (pokemon)|]] or [[Leaf (pokemon)|]][/td]
[/tr]
[/tbody]
[/table]
""",
        }
    )

    assert [section.title for section in page.sections] == ["Introduced in the games"]
    assert [tag.canonical_name for tag in page.sections[0].tags] == [
        "brock_(pokemon)",
        "red_(pokemon)",
        "leaf_(pokemon)",
    ]
