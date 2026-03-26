from danbooru_tag_groups.models import Page, Section, TagEntry


def test_resolve_implied_tags_propagates_groups_transitively() -> None:
    from danbooru_tag_groups.implications import resolve_implied_tags

    pages = [
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

    rows = resolve_implied_tags(
        pages=pages,
        implications=[
            {"antecedent_name": "red_skirt", "consequent_name": "skirt", "status": "active"},
            {"antecedent_name": "dark_red_skirt", "consequent_name": "red_skirt", "status": "active"},
        ],
    )

    resolved = {(row["canonical_name"], row.get("implied_via"), row["source"]) for row in rows}

    assert ("skirt", None, "wiki") in resolved
    assert ("red_skirt", "skirt", "implication") in resolved
    assert ("dark_red_skirt", "red_skirt", "implication") in resolved


def test_apply_implied_tags_adds_inherited_entries_to_sections() -> None:
    from danbooru_tag_groups.implications import apply_implied_tags

    pages = [
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

    expanded_pages = apply_implied_tags(
        pages=pages,
        implications=[{"antecedent_name": "red_skirt", "consequent_name": "skirt", "status": "active"}],
    )

    tags = expanded_pages[0].sections[0].tags

    assert [(tag.canonical_name, tag.source, tag.implied_via) for tag in tags] == [
        ("skirt", "wiki", None),
        ("red_skirt", "implication", "skirt"),
    ]
