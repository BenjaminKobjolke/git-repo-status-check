"""Integration tests for --pull-ask: a real origin, a real clone, real ahead/behind counts.

Requires ``git`` on PATH. No network -- the "remote" is a second directory reached over a
``file://`` URL, which is why ``protocol.file.allow`` is set in the shared helpers.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from git_repo_status_check.settings import Settings
from git_repo_status_check.upstream import scan_upstream

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

    results = scan_upstream(Settings(folders=(tmp_path / "roots",)))

    assert len(results) == 1
    assert results[0].path == clone
    assert results[0].behind == 1
    assert results[0].upstream.startswith("origin/")


def test_up_to_date_clone_is_not_reported(tmp_path: Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    _clone(origin, tmp_path / "roots" / "clone")
    assert scan_upstream(Settings(folders=(tmp_path / "roots",))) == []


def test_clone_only_ahead_is_not_reported(tmp_path: Path) -> None:
    # Ahead is not behind: nothing to pull, so the mode must stay quiet about it.
    origin = _init_repo(tmp_path / "origin")
    clone = _clone(origin, tmp_path / "roots" / "clone")
    _commit_more(clone, "local work")
    assert scan_upstream(Settings(folders=(tmp_path / "roots",))) == []


def test_repo_without_a_remote_is_ignored(tmp_path: Path) -> None:
    # No upstream at all -- must be skipped silently, not crash and not be reported.
    _init_repo(tmp_path / "roots" / "solo")
    assert scan_upstream(Settings(folders=(tmp_path / "roots",))) == []


def test_dirty_clone_still_reports_its_uncommitted_count(tmp_path: Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    clone = _clone(origin, tmp_path / "roots" / "clone")
    _commit_more(origin, "second")
    (clone / "scratch.txt").write_text("wip", encoding="utf-8")

    results = scan_upstream(Settings(folders=(tmp_path / "roots",)))

    assert len(results) == 1
    assert results[0].dirty_count == 1
    assert "1 uncommitted" in results[0].header()
