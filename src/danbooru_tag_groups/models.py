from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class TagEntry:
    label: str
    canonical_name: str
    url: str | None
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class Section:
    title: str
    path: list[str]
    tags: list[TagEntry] = field(default_factory=list)
    children: list["Section"] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "path": self.path,
            "tags": [tag.to_dict() for tag in self.tags],
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(slots=True)
class PageRef:
    title: str
    kind: str
    slug: str
    url: str


@dataclass(slots=True)
class Page:
    title: str
    kind: str
    slug: str
    url: str
    sections: list[Section]

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "kind": self.kind,
            "slug": self.slug,
            "url": self.url,
            "sections": [section.to_dict() for section in self.sections],
        }

