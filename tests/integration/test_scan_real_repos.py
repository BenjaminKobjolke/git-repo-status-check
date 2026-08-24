"""Integration tests: create real temp git repos and scan them end-to-end.

Requires ``git`` on PATH. Skipped automatically if git is missing.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from git_repo_status_check.scanner import scan_all, scan_repo
from git_repo_status_check.settings import Settings

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")

# Deterministic identity + no dependence on the developer's global git config.
_GIT_ENV_ARGS = (
    "-c",
    "user.email=test@example.com",
    "-c",
    "user.name=Test",
    "-c",
    "protocol.file.allow=always",
    "-c",
    "commit.gpgsign=false",
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ("git", "-C", str(repo), *_GIT_ENV_ARGS, *args),
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    (path / "readme.txt").write_text("hello", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "init")
    return path


def test_clean_repo_not_reported(tmp_path: Path) -> None:
    _init_repo(tmp_path / "clean")
    settings = Settings(folders=(tmp_path,))
    assert scan_all(settings) == []


def test_dirty_repo_counts_tracked_and_untracked(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "dirty")
    (repo / "readme.txt").write_text("changed", encoding="utf-8")  # tracked modification
    (repo / "new_file.txt").write_text("new", encoding="utf-8")  # untracked
    results = scan_all(Settings(folders=(tmp_path,)))
    assert len(results) == 1
    assert results[0].path == repo
    assert results[0].dirty_count == 2
    assert results[0].is_submodule is False


def test_scan_all_sorts_newest_change_first(tmp_path: Path) -> None:
    import os

    older = _init_repo(tmp_path / "older")
    newer = _init_repo(tmp_path / "newer")
    (older / "a.txt").write_text("x", encoding="utf-8")
    (newer / "b.txt").write_text("x", encoding="utf-8")
    os.utime(older / "a.txt", (1000, 1000))
    os.utime(newer / "b.txt", (5000, 5000))

    results = scan_all(Settings(folders=(tmp_path,)))
    assert [s.path for s in results] == [newer, older]


def test_submodule_reported_separately(tmp_path: Path) -> None:
    upstream = _init_repo(tmp_path / "upstream")
    main = _init_repo(tmp_path / "main")
    _git(main, "submodule", "add", upstream.as_uri(), "sub")
    _git(main, "commit", "-m", "add submodule")

    sub = main / "sub"
    (sub / "dirty.txt").write_text("x", encoding="utf-8")  # dirty inside the submodule

    statuses = scan_repo(main)
    submodules = [s for s in statuses if s.is_submodule]
    assert len(submodules) == 1
    assert submodules[0].path == sub
    assert submodules[0].dirty_count == 1
