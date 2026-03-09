from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="run tests that hit the live Danbooru site",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live: exercises the real Danbooru site")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--live"):
        return

    skip_live = pytest.mark.skip(reason="needs --live to run")
    for item in items:
        if item.get_closest_marker("live") is not None:
            item.add_marker(skip_live)
