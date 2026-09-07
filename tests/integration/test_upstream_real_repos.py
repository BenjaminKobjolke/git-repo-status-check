"""Integration tests for --pull-ask: a real origin, a real clone, real ahead/behind counts.

Requires ``git`` on PATH. No network -- the "remote" is a second directory reached over a
``file://`` URL, which is why ``protocol.file.allow`` is set in the shared helpers.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from git_repo_status_check.pusher import RepoAhead, measure_ahead
from git_repo_status_check.repo_actions import run_pull, run_push
from git_repo_status_check.settings import Settings
from git_repo_status_check.upstream import walk_found, walk_upstream

from .helpers import _GIT_ENV_ARGS, _git, _init_repo

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")


def _clone(origin: Path, into: Path) -> Path:
    into.parent.mkdir(parents=True, exist_ok=True)
    _git(into.parent, "clone", *_GIT_ENV_ARGS, origin.as_uri(), into.name)
    return into


def _commit_more(repo: Path, text: str) -> None:
    (repo / "readme.txt").write_text(text, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", text)


def test_clone_behind_its_origin_is_reported(tmp_path: Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    clone = _clone(origin, tmp_path / "roots" / "clone")
    _commit_more(origin, "second")

    results = list(walk_upstream(Settings(folders=(tmp_path / "roots",))))

    assert len(results) == 1
    assert results[0].path == clone
    assert results[0].behind == 1
    assert results[0].upstream.startswith("origin/")


def test_up_to_date_clone_is_not_reported(tmp_path: Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    _clone(origin, tmp_path / "roots" / "clone")
    assert list(walk_upstream(Settings(folders=(tmp_path / "roots",)))) == []


def test_clone_only_ahead_is_not_reported(tmp_path: Path) -> None:
    # Ahead is not behind: nothing to pull, so the mode must stay quiet about it.
    origin = _init_repo(tmp_path / "origin")
    clone = _clone(origin, tmp_path / "roots" / "clone")
    _commit_more(clone, "local work")
    assert list(walk_upstream(Settings(folders=(tmp_path / "roots",)))) == []


def test_repo_without_a_remote_is_ignored(tmp_path: Path) -> None:
    # No upstream at all -- must be skipped silently, not crash and not be reported.
    _init_repo(tmp_path / "roots" / "solo")
    assert list(walk_upstream(Settings(folders=(tmp_path / "roots",)))) == []


def test_dirty_clone_still_reports_its_uncommitted_count(tmp_path: Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    clone = _clone(origin, tmp_path / "roots" / "clone")
    _commit_more(origin, "second")
    (clone / "scratch.txt").write_text("wip", encoding="utf-8")

    results = list(walk_upstream(Settings(folders=(tmp_path / "roots",))))

    assert len(results) == 1
    assert results[0].dirty_count == 1
    assert "1 uncommitted" in results[0].header()


def _ahead_of(root: Path) -> list[RepoAhead]:
    return list(walk_found(Settings(folders=(root,)), measure_ahead))


def test_clone_ahead_of_its_origin_is_reported_for_push(tmp_path: Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    clone = _clone(origin, tmp_path / "roots" / "clone")
    _commit_more(clone, "local work")

    results = _ahead_of(tmp_path / "roots")

    assert len(results) == 1
    assert results[0].path == clone
    assert results[0].ahead == 1
    assert results[0].upstream is not None
    assert results[0].push_args() == ("push",)


def test_up_to_date_clone_has_nothing_to_push(tmp_path: Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    _clone(origin, tmp_path / "roots" / "clone")
    assert _ahead_of(tmp_path / "roots") == []


def test_branch_never_pushed_offers_push_u(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "roots" / "fresh")
    _git(repo, "remote", "add", "origin", (tmp_path / "nowhere").as_uri())

    results = _ahead_of(tmp_path / "roots")

    assert len(results) == 1
    assert results[0].upstream is None
    assert results[0].push_args() == ("push", "-u", "origin", "main")


def test_repo_without_a_remote_has_nothing_to_push(tmp_path: Path) -> None:
    _init_repo(tmp_path / "roots" / "solo")
    assert _ahead_of(tmp_path / "roots") == []


def test_push_sends_local_commits_to_a_bare_origin(tmp_path: Path) -> None:
    # Bare: a non-bare origin refuses pushes to its checked-out branch.
    seed = _init_repo(tmp_path / "seed")
    bare = tmp_path / "origin.git"
    _git(tmp_path, "clone", "--bare", *_GIT_ENV_ARGS, seed.as_uri(), bare.name)
    clone = _clone(bare, tmp_path / "roots" / "clone")
    _commit_more(clone, "local work")

    assert run_push(clone, ("push",)) is True
    assert _git(bare, "rev-parse", "main") == _git(clone, "rev-parse", "HEAD")


def test_pull_succeeds_over_line_ending_noise(tmp_path: Path) -> None:
    # LF blob, CRLF worktree copy, conversion off: the scanner calls the clone clean, but a
    # plain `git pull` refuses to overwrite the "modified" file. The pull must clear that
    # noise itself instead of dead-ending on a repo the tool just reported as clean.
    origin = _init_repo(tmp_path / "origin")
    (origin / "readme.txt").write_bytes(b"one\ntwo\n")
    _git(origin, "commit", "-am", "lf lines")
    clone = _clone(origin, tmp_path / "roots" / "clone")
    _git(clone, "config", "core.autocrlf", "false")
    (clone / "readme.txt").write_bytes(b"one\r\ntwo\r\n")
    (origin / "readme.txt").write_bytes(b"one\nthree\n")
    _git(origin, "commit", "-am", "upstream edit")

    assert run_pull(clone) is True
    assert (clone / "readme.txt").read_bytes() == b"one\nthree\n"
