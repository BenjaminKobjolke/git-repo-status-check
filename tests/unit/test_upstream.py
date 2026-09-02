"""Unit tests for the --pull-ask walk: which repos it reports behind. Git calls are stubbed.

The menu loop that consumes this walk is tested in ``test_pull_interactive``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo_status_check import scanner, upstream
from git_repo_status_check.settings import Settings

from .helpers import _stub_upstream_git as _stub_git


def _scan(monkeypatch: pytest.MonkeyPatch, repos: list[Path]) -> list[upstream.RepoUpstream]:
    monkeypatch.setattr(scanner, "find_repos", lambda *_a, **_k: iter(repos))
    return list(upstream.walk_upstream(Settings(folders=(Path("root"),))))


def test_behind_and_ahead_counts_are_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, counts="2\t3\n")
    results = _scan(monkeypatch, [Path("repo0")])
    assert len(results) == 1
    assert results[0].behind == 2
    assert results[0].upstream == "origin/main"


def test_repo_level_with_upstream_is_not_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, counts="0\t0\n")
    assert _scan(monkeypatch, [Path("repo0")]) == []


def test_repo_without_tracking_branch_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_git(monkeypatch, upstream_name=None)
    assert _scan(monkeypatch, [Path("repo0")]) == []
    # Bailing out early also means the expensive rev-list is never run.
    assert not [args for args in calls if args[0] == "rev-list"]


def test_unreadable_rev_list_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, counts=None)
    assert _scan(monkeypatch, [Path("repo0")]) == []


def test_unparsable_rev_list_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    # An answer that is not "<int>\t<int>" must not crash the whole walk.
    _stub_git(monkeypatch, counts="nonsense\n")
    assert _scan(monkeypatch, [Path("repo0")]) == []


def test_results_arrive_in_walk_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not sorted by staleness: the menu comes up mid-walk, so there is nothing to sort."""
    behind = iter(["1\t0\n", "7\t0\n", "3\t0\n"])
    monkeypatch.setattr(upstream, "dirty_info", lambda _repo: (0, 0.0))
    monkeypatch.setattr(
        upstream,
        "run_git",
        lambda _repo, args, quiet=False: (
            "origin/main\n"
            if args[0] == "rev-parse"
            else next(behind)
            if args[0] == "rev-list"
            else ""
        ),
    )
    results = _scan(monkeypatch, [Path("a"), Path("b"), Path("c")])
    assert [r.behind for r in results] == [1, 7, 3]


def test_header_notes_uncommitted_files(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch)
    monkeypatch.setattr(upstream, "dirty_info", lambda _repo: (4, 0.0))
    header = _scan(monkeypatch, [Path("repo0")])[0].header()
    assert "2 commit" in header
    assert "origin/main" in header
    assert "4 uncommitted" in header


def test_header_omits_the_dirty_note_when_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch)
    assert "uncommitted" not in _scan(monkeypatch, [Path("repo0")])[0].header()
