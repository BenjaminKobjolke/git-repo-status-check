"""Unit tests for the ``scan_all`` walk itself -- its filter and its checked-repo hook.

Separate from ``test_scanner`` (which covers the git-output parsing) because these tests stub
the walk out entirely and only assert what ``scan_all`` does around each repo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo_status_check import scanner
from git_repo_status_check.models import RepoStatus
from git_repo_status_check.settings import Settings

_SETTINGS = Settings(folders=(Path("root"),))


def _one_repo_walk(monkeypatch: pytest.MonkeyPatch, dirty: bool) -> None:
    """Reduce the walk to a single repo whose dirtiness the test dictates.

    ``find_repos`` is the stub point, not ``walk_repos``: the skip and the progress
    announcement live in ``walk_repos``, so replacing it would take them out of the test.
    """
    monkeypatch.setattr(scanner, "find_repos", lambda *_a, **_k: iter([Path("repo0")]))
    status = RepoStatus(path=Path("repo0"), dirty_count=1, latest_change=0.0)
    monkeypatch.setattr(scanner, "scan_repo", lambda _repo: [status] if dirty else [])


def test_scan_all_skips_the_repos_the_filter_names(monkeypatch: pytest.MonkeyPatch) -> None:
    _one_repo_walk(monkeypatch, dirty=True)
    monkeypatch.setattr(
        scanner, "scan_repo", lambda _repo: pytest.fail("a skipped repo must cost no git call")
    )
    assert scanner.scan_all(_SETTINGS, skip=lambda _repo: "muted for 2 days") == []


def test_scan_all_keeps_the_repos_the_filter_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    _one_repo_walk(monkeypatch, dirty=True)
    assert len(scanner.scan_all(_SETTINGS, skip=lambda _repo: None)) == 1


def test_a_held_back_repo_is_never_announced(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bug this guards: a skipped repo that still prints a progress line makes a re-run
    look exactly like a full scan, so the saved work is invisible."""
    _one_repo_walk(monkeypatch, dirty=True)
    announced: list[Path] = []
    scanner.scan_all(_SETTINGS, on_repo=announced.append, skip=lambda _repo: "muted for 2 days")
    assert announced == []


def test_a_checked_repo_is_announced(monkeypatch: pytest.MonkeyPatch) -> None:
    _one_repo_walk(monkeypatch, dirty=True)
    announced: list[Path] = []
    scanner.scan_all(_SETTINGS, on_repo=announced.append, skip=lambda _repo: None)
    assert announced == [Path("repo0")]


def test_scan_all_reports_a_clean_repo_as_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    _one_repo_walk(monkeypatch, dirty=False)
    checked: list[Path] = []
    assert scanner.scan_all(_SETTINGS, on_clean=checked.append) == []
    assert checked == [Path("repo0")]


def test_scan_all_leaves_a_dirty_repo_unchecked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Something is still to be done here, so the next run must ask about it again."""
    _one_repo_walk(monkeypatch, dirty=True)
    checked: list[Path] = []
    scanner.scan_all(_SETTINGS, on_clean=checked.append)
    assert checked == []
