from __future__ import annotations

from collections.abc import Iterable
import re
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from danbooru_tag_groups.models import Page, PageRef, Section, TagEntry


SUPPORTED_HOST = "danbooru.donmai.us"
WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]")
HEADING_RE = re.compile(r"^h([1-6])(?:#.*?)?\.\s*(.+)$")
TOPIC_MARKUP_RE = re.compile(r"\[/?tn\]")
EXPAND_RE = re.compile(r"^\[expand(?:=([^\]]*))?\]$")


def parse_index_page(html: str, *, root_url: str) -> list[PageRef]:
    soup = BeautifulSoup(html, "html.parser")
    container = _find_container(soup)
    page_refs: list[PageRef] = []
    seen: set[str] = set()

    for anchor in container.find_all("a", href=True):
        absolute_url = _normalize_page_url(anchor["href"], root_url)
        if absolute_url is None:
            continue
        slug = _extract_slug(absolute_url)
        if slug is None or slug in seen:
            continue
        kind = "tag_group" if slug.startswith("tag_group:") else "list"
        page_refs.append(
            PageRef(
                title=_title_from_slug(slug),
                kind=kind,
                slug=slug,
                url=absolute_url,
            )
        )
        seen.add(slug)

    return page_refs


def parse_group_page(html: str, *, url: str) -> Page:
    soup = BeautifulSoup(html, "html.parser")
    container = _find_container(soup)
    title_tag = soup.find("h1") or container.find(["h1", "h2", "h3"]) or soup.find(["h2", "h3"])
    if title_tag is None:
        raise ValueError("Could not determine page title from heading")

    slug = _extract_slug(url)
    if slug is None:
        raise ValueError(f"Unsupported page url: {url}")

    page_title = _title_from_heading_or_slug(title_tag.get_text(" ", strip=True), slug)
    page_kind = "tag_group" if slug.startswith("tag_group:") else "list"
    root_sections: list[Section] = []
    stack: list[tuple[int, Section]] = []
    skip_level: int | None = None

    for element in _iter_content_elements(container):
        if _is_heading(element):
            level = int(element.name[1])
            heading_title = _clean_text(element.get_text(" ", strip=True))
            if skip_level is not None and level > skip_level:
                continue
            skip_level = None

            if heading_title.lower() == "see also":
                skip_level = level
                stack = [entry for entry in stack if entry[0] < level]
                continue

            section = Section(title=heading_title, path=[], tags=[], children=[])
            while stack and stack[-1][0] >= level:
                stack.pop()
            if stack:
                stack[-1][1].children.append(section)
            else:
                root_sections.append(section)
            stack.append((level, section))
            continue

        if element.name in {"ul", "ol"} and stack and skip_level is None:
            section = stack[-1][1]
            existing = {tag.canonical_name for tag in section.tags}
            for tag in _parse_list_tags(element, url):
                if tag.canonical_name in existing:
                    continue
                section.tags.append(tag)
                existing.add(tag.canonical_name)

    _apply_paths(root_sections, [page_title])
    return Page(title=page_title, kind=page_kind, slug=slug, url=url, sections=root_sections)


def parse_index_body(body: str) -> list[PageRef]:
    page_refs: list[PageRef] = []
    seen: set[str] = set()

    for line in _iter_body_lines(body):
        for target, _alias in _extract_wiki_links(line):
            slug = _slug_from_wiki_title(target)
            if slug is None or slug in seen:
                continue
            if not slug.startswith("tag_group:") and not slug.startswith("list_of_"):
                continue
            kind = "tag_group" if slug.startswith("tag_group:") else "list"
            page_refs.append(
                PageRef(
                    title=_title_from_slug(slug),
                    kind=kind,
                    slug=slug,
                    url=_wiki_page_url(slug),
                )
            )
            seen.add(slug)

    return page_refs


def parse_wiki_page_record(record: dict[str, object]) -> Page:
    raw_title = record.get("title")
    raw_body = record.get("body")
    if not isinstance(raw_title, str) or not isinstance(raw_body, str):
        raise ValueError("Wiki page record must include string title and body fields")

    slug = _slug_from_wiki_title(raw_title)
    if slug is None:
        raise ValueError(f"Unsupported wiki page title: {raw_title}")

    page_kind = "tag_group" if slug.startswith("tag_group:") else "list"
    page_title = _title_from_slug(slug)
    root_sections: list[Section] = []
    stack: list[tuple[int, Section]] = []
    skip_level: int | None = None
    in_table = False
    table_headers: list[str] = []
    table_column_index = 0

    for line in _iter_body_lines(raw_body):
        heading_match = HEADING_RE.match(line)
        if heading_match:
            level = int(heading_match.group(1))
            heading_title = _clean_heading_text(heading_match.group(2))
            if skip_level is not None and level > skip_level:
                continue
            skip_level = None
            in_table = False
            table_headers = []
            table_column_index = 0

            if heading_title.lower() == "see also":
                skip_level = level
                stack = [entry for entry in stack if entry[0] < level]
                continue

            section = Section(title=heading_title, path=[], tags=[], children=[])
            while stack and stack[-1][0] >= level:
                stack.pop()
            if stack:
                stack[-1][1].children.append(section)
            else:
                root_sections.append(section)
            stack.append((level, section))
            continue

        if skip_level is not None:
            continue

        if line == "[table]":
            in_table = True
            table_headers = []
            table_column_index = 0
            continue

        if line == "[/table]":
            in_table = False
            table_headers = []
            table_column_index = 0
            continue

        if in_table:
            if line == "[tr]":
                table_column_index = 0
                continue
            if line == "[/tr]":
                table_column_index = 0
                continue
            if line.startswith("[th]") and line.endswith("[/th]"):
                table_headers.append(_clean_heading_text(line[4:-5]))
                table_column_index += 1
                continue
            if line.startswith("[td]") and line.endswith("[/td]"):
                header = table_headers[table_column_index] if table_column_index < len(table_headers) else ""
                if _table_header_wants_links(header):
                    section = stack[-1][1] if stack else _ensure_general_section(root_sections)
                    existing = {tag.canonical_name for tag in section.tags}
                    for tag in _parse_dtext_inline_links(line[4:-5]):
                        if tag.canonical_name in existing:
                            continue
                        section.tags.append(tag)
                        existing.add(tag.canonical_name)
                table_column_index += 1
                continue

        if not line.startswith("*"):
            continue

        section = stack[-1][1] if stack else _ensure_general_section(root_sections)
        existing = {tag.canonical_name for tag in section.tags}
        for tag in _parse_dtext_list_item(line):
            if tag.canonical_name in existing:
                continue
            section.tags.append(tag)
            existing.add(tag.canonical_name)

    _apply_paths(root_sections, [page_title])
    return Page(title=page_title, kind=page_kind, slug=slug, url=_wiki_page_url(slug), sections=root_sections)


def _find_container(soup: BeautifulSoup) -> Tag:
    return soup.find(id="wiki-page-body") or soup.body or soup


def _iter_content_elements(container: Tag) -> Iterable[Tag]:
    for element in container.find_all(["h2", "h3", "h4", "h5", "h6", "ul", "ol"]):
        yield element


def _is_heading(tag: Tag) -> bool:
    return tag.name in {"h2", "h3", "h4", "h5", "h6"}


def _parse_list_tags(list_tag: Tag, page_url: str) -> list[TagEntry]:
    entries: list[TagEntry] = []
    for item in list_tag.find_all("li", recursive=False):
        anchors = [
            anchor
            for anchor in item.find_all("a", href=True)
            if _is_leaf_wiki_page(anchor["href"], page_url)
        ]
        if not anchors:
            continue
        note = _extract_note_after_last_anchor(item, anchors[-1])
        for anchor in anchors:
            href = urljoin(page_url, anchor["href"])
            slug = _extract_slug(href)
            if slug is None:
                continue
            entries.append(
                TagEntry(
                    label=_clean_text(anchor.get_text(" ", strip=True)),
                    canonical_name=_canonical_name_from_slug_or_label(slug, anchor.get_text(" ", strip=True)),
                    url=href,
                    notes=note,
                )
            )
    return entries


def _extract_note_after_last_anchor(item: Tag, anchor: Tag) -> str | None:
    note_parts: list[str] = []
    for sibling in anchor.next_siblings:
        text = sibling.get_text(" ", strip=True) if isinstance(sibling, Tag) else str(sibling)
        cleaned = _clean_text(text)
        if cleaned:
            note_parts.append(cleaned)

    if not note_parts:
        return None

    note = " ".join(note_parts).strip()
    if note in {"/", "|"}:
        return None
    if note.startswith("(") and note.endswith(")"):
        note = note[1:-1].strip()
    return note or None


def _apply_paths(sections: list[Section], prefix: list[str]) -> None:
    for section in sections:
        section.path = [*prefix, section.title]
        _apply_paths(section.children, section.path)


def _normalize_page_url(href: str, root_url: str) -> str | None:
    absolute_url = urljoin(root_url, href)
    parsed = urlparse(absolute_url)
    if parsed.netloc != SUPPORTED_HOST:
        return None
    slug = _extract_slug(absolute_url)
    if slug is None:
        return None
    if not slug.startswith("tag_group:") and not slug.startswith("list_of_"):
        return None
    return absolute_url


def _is_leaf_wiki_page(href: str, page_url: str) -> bool:
    absolute_url = urljoin(page_url, href)
    parsed = urlparse(absolute_url)
    if parsed.netloc != SUPPORTED_HOST:
        return False
    slug = _extract_slug(absolute_url)
    return slug is not None and not slug.startswith("tag_group:") and not slug.startswith("list_of_")


def _extract_slug(url: str) -> str | None:
    parsed = urlparse(url)
    marker = "/wiki_pages/"
    if marker not in parsed.path:
        return None
    slug = unquote(parsed.path.split(marker, 1)[1])
    if not slug.startswith("tag_group:") and not slug.startswith("list_of_") and ":" in slug:
        return slug
    if slug.startswith("tag_group:") or slug.startswith("list_of_"):
        return slug
    if slug:
        return slug
    return None


def _title_from_heading_or_slug(heading: str, slug: str) -> str:
    normalized = heading.strip()
    if normalized.lower().startswith("tag group:"):
        return _title_from_slug(slug)
    return _title_case_words(normalized.replace("_", " "))


def _title_from_slug(slug: str) -> str:
    if slug.startswith("tag_group:"):
        slug = slug.split(":", 1)[1]
    return _title_case_words(slug.replace("_", " "))


def _title_case_words(text: str) -> str:
    return " ".join(part.capitalize() if part else part for part in text.split())


def _canonical_name_from_slug_or_label(slug: str, label: str) -> str:
    if slug.startswith("tag_group:") or slug.startswith("list_of_"):
        return _normalize_label(label)
    return slug


def _normalize_label(text: str) -> str:
    return _clean_text(text).lower().replace(" ", "_")


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _ensure_general_section(root_sections: list[Section]) -> Section:
    for section in root_sections:
        if section.title == "General":
            return section
    section = Section(title="General", path=[], tags=[], children=[])
    root_sections.append(section)
    return section


def _iter_body_lines(body: str) -> Iterable[str]:
    expand_skip_stack: list[bool] = []
    for raw_line in body.replace("\r\n", "\n").split("\n"):
        for part in raw_line.replace("[/expand]", "\n[/expand]\n").split("\n"):
            line = part.strip()
            if not line:
                continue
            expand_match = EXPAND_RE.match(line)
            if expand_match:
                title = expand_match.group(1) or ""
                parent_skipped = any(expand_skip_stack)
                expand_skip_stack.append(parent_skipped or _is_non_content_expand(title))
                continue
            if line == "[/expand]":
                if expand_skip_stack:
                    expand_skip_stack.pop()
                continue
            if any(expand_skip_stack):
                continue
            yield line


def _extract_wiki_links(text: str) -> list[tuple[str, str | None]]:
    return [(target.strip(), alias) for target, alias in WIKI_LINK_RE.findall(text)]


def _slug_from_wiki_title(title: str) -> str | None:
    normalized = _normalize_label(title)
    if not normalized:
        return None
    return normalized.replace("tag_group_", "tag_group:", 1) if normalized.startswith("tag_group_") else normalized


def _wiki_page_url(slug: str) -> str:
    return f"https://{SUPPORTED_HOST}/wiki_pages/{slug}"


def _parse_dtext_list_item(line: str) -> list[TagEntry]:
    content = line.lstrip("*").strip()
    primary_text, note_text = _split_primary_and_note(content)
    note = _clean_note_text(note_text)
    return _parse_dtext_inline_links(primary_text, note=note)


def _parse_dtext_inline_links(content: str, *, note: str | None = None) -> list[TagEntry]:
    entries: list[TagEntry] = []
    for target, alias in _extract_wiki_links(content):
        slug = _slug_from_wiki_title(target)
        if slug is None or slug.startswith("tag_group:") or slug.startswith("list_of_"):
            continue
        entries.append(
            TagEntry(
                label=_display_label(target, alias),
                canonical_name=slug,
                url=_wiki_page_url(slug),
                notes=note,
            )
        )
    return entries


def _split_primary_and_note(content: str) -> tuple[str, str]:
    in_link = False
    index = 0
    while index < len(content):
        if content.startswith("[[", index):
            in_link = True
            index += 2
            continue
        if content.startswith("]]", index):
            in_link = False
            index += 2
            continue
        if not in_link and content.startswith("[tn]", index):
            return content[:index].rstrip(), content[index:]
        if not in_link and content[index] == "(":
            return content[:index].rstrip(), content[index:]
        index += 1
    return content, ""


def _clean_note_text(note_text: str) -> str | None:
    if not note_text:
        return None
    cleaned = TOPIC_MARKUP_RE.sub("", note_text).strip()
    cleaned = cleaned.lstrip("|").strip()
    cleaned = WIKI_LINK_RE.sub(lambda match: _display_label(match.group(1), match.group(2)), cleaned)
    cleaned = _clean_text(cleaned)
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1].strip()
    return cleaned or None


def _display_label(target: str, alias: str | None) -> str:
    if alias is not None and alias != "":
        return _clean_text(alias)
    if alias == "":
        target = re.sub(r"\s+\([^)]*\)$", "", target)
    return _clean_text(target)


def _clean_heading_text(text: str) -> str:
    cleaned = WIKI_LINK_RE.sub(lambda match: _display_label(match.group(1), match.group(2)), text)
    cleaned = TOPIC_MARKUP_RE.sub("", cleaned)
    return _clean_text(cleaned)


def _is_non_content_expand(title: str) -> bool:
    normalized = _clean_text(title).lower()
    return normalized in {"table of contents", "toc"}


def _table_header_wants_links(header: str) -> bool:
    normalized = _clean_text(header).lower()
    return any(
        keyword in normalized for keyword in ("tag", "character", "children", "child", "family", "member")
    )
