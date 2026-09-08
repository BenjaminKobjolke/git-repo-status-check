"""Unit tests for the --push-ask measurement: which repos have unpushed commits. Git stubbed.

The menu loop that consumes this is tested in ``test_push_interactive``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo_status_check import pusher, upstream


def _stub_git(
    monkeypatch: pytest.MonkeyPatch,
    *,
    upstream_name: str | None = "origin/main",
    counts: str | None = "0\t2\n",
    branch: str | None = "main\n",
    remotes: str | None = "origin\n",
    commit_count: str | None = "3\n",
) -> list[tuple[str, ...]]:
    """Record every git call; answer each command ``measure_ahead`` may issue.

    ``None`` models the real failure modes: no tracking branch, a detached HEAD
    (``symbolic-ref`` fails), no remote, an unborn branch (``rev-list`` fails).
    """
    calls: list[tuple[str, ...]] = []

    def run_git(
        _repo: Path, args: tuple[str, ...], quiet: bool = False, timeout: float | None = None
    ) -> str | None:
        calls.append(args)
        if args[0] == "rev-parse":
            return None if upstream_name is None else f"{upstream_name}\n"
        if args[0] == "rev-list" and "--left-right" in args:
            return counts
        if args[0] == "rev-list":
            return commit_count
        if args[0] == "symbolic-ref":
            return branch
        if args[0] == "remote":
            return remotes
        return ""

    monkeypatch.setattr(upstream, "run_git", run_git)
    monkeypatch.setattr(pusher, "run_git", run_git)
    monkeypatch.setattr(pusher, "dirty_info", lambda _repo: (0, 0.0))
    return calls


def test_repo_ahead_of_its_upstream_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_git(monkeypatch)
    found = pusher.measure_ahead(Path("repo0"))
    assert found is not None
    assert found.ahead == 2
    assert found.upstream == "origin/main"
    assert found.push_args() == ("push",)
    assert "2 commit(s) ahead of origin/main" in found.header()
    # Local refs only: this mode never fetches.
    assert not [args for args in calls if args[0] == "fetch"]


def test_repo_level_with_upstream_is_not_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, counts="3\t0\n")
    assert pusher.measure_ahead(Path("repo0")) is None


def test_branch_without_upstream_offers_push_u(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, upstream_name=None)
    found = pusher.measure_ahead(Path("repo0"))
    assert found is not None
    assert found.upstream is None
    assert found.ahead == 3
    assert found.push_args() == ("push", "-u", "origin", "main")
    assert "no upstream" in found.header()


def test_first_remote_is_the_push_u_target(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, upstream_name=None, remotes="fork\norigin\n")
    found = pusher.measure_ahead(Path("repo0"))
    assert found is not None
    assert found.remote == "fork"


def test_branch_without_a_remote_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, upstream_name=None, remotes="")
    assert pusher.measure_ahead(Path("repo0")) is None


def test_detached_head_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, upstream_name=None, branch=None)
    assert pusher.measure_ahead(Path("repo0")) is None


def test_unborn_branch_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, upstream_name=None, commit_count=None)
    assert pusher.measure_ahead(Path("repo0")) is None


def test_header_notes_uncommitted_files(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch)
    monkeypatch.setattr(pusher, "dirty_info", lambda _repo: (4, 0.0))
    found = pusher.measure_ahead(Path("repo0"))
    assert found is not None
    assert "4 uncommitted" in found.header()
