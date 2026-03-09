from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from danbooru_tag_groups.models import Page, Section


def build_hierarchical_document(*, pages: list[Page], root_url: str) -> dict[str, object]:
    return {
        "source": {
            "root_url": root_url,
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "pages_scraped": len(pages),
            "tool_version": "1",
        },
        "pages": [page.to_dict() for page in pages],
    }


def build_flat_rows(pages: list[Page]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for page in pages:
        for section in page.sections:
            rows.extend(_section_rows(page, section))
    return rows


def export_outputs(*, pages: list[Page], output_dir: Path, root_url: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    hierarchical_path = output_dir / "tag_groups_hierarchical.json"
    flat_path = output_dir / "tag_groups_flat.jsonl"

    hierarchical_path.write_text(
        json.dumps(build_hierarchical_document(pages=pages, root_url=root_url), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    flat_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in build_flat_rows(pages)) + ("\n" if pages else ""),
        encoding="utf-8",
    )
    return hierarchical_path, flat_path


def _section_rows(page: Page, section: Section) -> list[dict[str, object]]:
    rows = [
        {
            "page_title": page.title,
            "page_kind": page.kind,
            "page_slug": page.slug,
            "page_url": page.url,
            "section_title": section.title,
            "section_path": section.path,
            "tag_label": tag.label,
            "canonical_name": tag.canonical_name,
            "tag_url": tag.url,
            "notes": tag.notes,
        }
        for tag in section.tags
    ]
    for child in section.children:
        rows.extend(_section_rows(page, child))
    return rows

