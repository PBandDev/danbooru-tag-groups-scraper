from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Sequence

from danbooru_tag_groups.export import export_outputs
from danbooru_tag_groups.fetch import scrape_site


DEFAULT_ROOT_URL = "https://danbooru.donmai.us/wiki_pages/tag_groups"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="danbooru-tag-groups")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scrape_parser = subparsers.add_parser("scrape", help="Scrape Danbooru tag groups")
    scrape_parser.add_argument("--root-url", default=DEFAULT_ROOT_URL)
    scrape_parser.add_argument("--output-dir", required=True)
    scrape_parser.add_argument("--timeout", type=float, default=20.0)
    scrape_parser.add_argument("--delay-ms", type=int, default=250)
    scrape_parser.add_argument("--max-pages", type=int, default=None)
    scrape_parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command != "scrape":
        parser.error(f"Unsupported command: {args.command}")

    pages = asyncio.run(
        scrape_site(
            root_url=args.root_url,
            timeout=args.timeout,
            delay_ms=args.delay_ms,
            max_pages=args.max_pages,
            verbose=args.verbose,
        )
    )
    export_outputs(pages=pages, output_dir=Path(args.output_dir), root_url=args.root_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
