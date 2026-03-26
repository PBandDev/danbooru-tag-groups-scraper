from __future__ import annotations

from pathlib import Path
import tomllib


pytest_plugins = ["pytester"]


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_live_tests_are_skipped_without_live_flag(pytester) -> None:
    conftest_path = REPO_ROOT / "tests" / "conftest.py"
    pytester.makeconftest(conftest_path.read_text(encoding="utf-8"))
    pytester.makepyfile(
        """
        import pytest


        @pytest.mark.live
        def test_live():
            assert True
        """
    )

    result = pytester.runpytest("-q")

    result.assert_outcomes(skipped=1)


def test_live_tests_run_with_live_flag(pytester) -> None:
    conftest_path = REPO_ROOT / "tests" / "conftest.py"
    pytester.makeconftest(conftest_path.read_text(encoding="utf-8"))
    pytester.makepyfile(
        """
        import pytest


        @pytest.mark.live
        def test_live():
            assert True
        """
    )

    result = pytester.runpytest("--live", "-q")

    result.assert_outcomes(passed=1)


def test_pyproject_declares_mit_license_metadata() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["license"] == "MIT"
    assert "License :: OSI Approved :: MIT License" in project["classifiers"]
    assert "Programming Language :: Python :: 3.12" in project["classifiers"]
    assert "Operating System :: OS Independent" in project["classifiers"]


def test_ci_workflow_runs_offline_tests_and_build() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "python-version: \"3.12\"" in workflow or "python-version: '3.12'" in workflow
    assert "uv sync --frozen --extra dev" in workflow
    assert "uv run python -m pytest -q" in workflow
    assert "uv build" in workflow


def test_publish_workflow_uses_versioned_monthly_releases() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "publish-data.yml").read_text(encoding="utf-8")

    assert 'cron: "17 6 1 * *"' in workflow
    assert "python-version: \"3.12\"" in workflow or "python-version: '3.12'" in workflow
    assert "ref: main" in workflow
    assert "concurrency:" in workflow
    assert "uv run python -m pytest -q" in workflow
    assert "data-" in workflow
    assert "git rev-parse HEAD" in workflow
    assert 'gh release delete "${RELEASE_TAG}" --cleanup-tag --yes' in workflow
    assert 'gh release create "${RELEASE_TAG}"' in workflow
    assert "for attempt in 1 2 3 4 5" in workflow
    assert 'sleep 5' in workflow
    assert 'gh release edit "${RELEASE_TAG}"' not in workflow
    assert "latest-data" not in workflow


def test_readme_documents_offline_and_live_test_commands() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()

    assert "uv run python -m pytest -q" in readme
    assert "uv run python -m pytest -q --live" in readme
    assert "same-month reruns recreate that month's release" in readme


def test_readme_documents_default_implication_resolution() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()

    assert "tag implications" in readme
    assert "variant tags" in readme
    assert '"source": "implication"' in readme
