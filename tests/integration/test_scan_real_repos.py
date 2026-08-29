"""Integration tests: create real temp git repos and scan them end-to-end.

Requires ``git`` on PATH. Skipped automatically if git is missing.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from git_repo_status_check.line_endings import repair
from git_repo_status_check.scanner import (
    changed_file_ages,
    changed_paths,
    line_ending_only_paths,
    scan_all,
    scan_repo,
)
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


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(repo), *_GIT_ENV_ARGS, *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


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


def _autocrlf(repo: Path) -> str:
    """The repo's own core.autocrlf value ("" when unset locally)."""
    return _git(repo, "config", "--local", "--get", "--default", "", "core.autocrlf")


def _init_lf_repo(path: Path) -> Path:
    """A repo holding two LF-committed files, with autocrlf off so git sees worktree bytes."""
    repo = _init_repo(path)
    _git(repo, "config", "core.autocrlf", "false")
    (repo / "endings.txt").write_bytes(b"one\ntwo\n")
    (repo / "content.txt").write_bytes(b"one\ntwo\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "lf files")
    return repo


def test_line_ending_only_repo_not_reported(tmp_path: Path) -> None:
    repo = _init_lf_repo(tmp_path / "crlf")
    (repo / "endings.txt").write_bytes(b"one\r\ntwo\r\n")  # same content, CRLF instead of LF
    assert scan_all(Settings(folders=(tmp_path,))) == []


def test_real_edit_survives_the_line_ending_filter(tmp_path: Path) -> None:
    repo = _init_lf_repo(tmp_path / "mixed")
    (repo / "endings.txt").write_bytes(b"one\r\ntwo\r\n")  # noise
    (repo / "content.txt").write_bytes(b"one\nedited\n")  # genuine edit

    results = scan_all(Settings(folders=(tmp_path,)))
    assert len(results) == 1
    assert results[0].dirty_count == 1
    assert [f.path for f in changed_file_ages(repo)] == ["content.txt"]


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


def test_spaced_filename_line_ending_noise_is_filtered(tmp_path: Path) -> None:
    # The line-based porcelain quotes "VD examples.txt"; only -z makes it matchable.
    repo = _init_lf_repo(tmp_path / "spaced")
    spaced = repo / "VD examples.txt"
    spaced.write_bytes(b"one\ntwo\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "spaced lf file")
    spaced.write_bytes(b"one\r\ntwo\r\n")
    assert scan_all(Settings(folders=(tmp_path,))) == []


def test_non_ascii_filename_scans_without_a_decode_error(tmp_path: Path) -> None:
    # This name's UTF-8 contains 0x8D, undefined in cp1252 — a locale decode aborts the scan.
    repo = _init_repo(tmp_path / "unicode")
    (repo / "不.txt").write_text("x", encoding="utf-8")
    files = changed_file_ages(repo)
    assert [f.path for f in files] == ["不.txt"]
    assert files[0].mtime is not None


def test_staged_rename_is_one_entry_with_the_destination_path(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "renamed")
    _git(repo, "mv", "readme.txt", "readme renamed.txt")
    files = changed_file_ages(repo)
    assert [f.path for f in files] == ["readme renamed.txt"]
    assert files[0].code.startswith("R")


def test_repair_makes_a_noisy_repo_clean_without_touching_files(tmp_path: Path) -> None:
    # LF blobs, CRLF worktree, conversion off: git calls every file modified. Turning
    # core.autocrlf on normalizes the worktree copy back to the blobs, rewriting nothing.
    repo = _init_lf_repo(tmp_path / "repairable")
    for name in ("endings.txt", "content.txt"):
        (repo / name).write_bytes(b"one\r\ntwo\r\n")
    before = {f.name: f.read_bytes() for f in repo.glob("*.txt")}
    noisy = line_ending_only_paths(repo)
    assert noisy == {"endings.txt", "content.txt"}

    result = repair(repo, noisy)
    assert result.autocrlf == "true"
    assert changed_paths(repo) == set()
    assert {f.name: f.read_bytes() for f in repo.glob("*.txt")} == before


def test_repair_rolls_back_when_gitattributes_wins(tmp_path: Path) -> None:
    # `* -text` disables conversion outright, so no core.autocrlf value can clear the noise;
    # the repo's own setting must be left exactly as it was found.
    repo = _init_lf_repo(tmp_path / "attrs")
    (repo / ".gitattributes").write_text("* -text\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-m", "attrs")
    (repo / "endings.txt").write_bytes(b"one\r\ntwo\r\n")
    noisy = line_ending_only_paths(repo)
    assert noisy == {"endings.txt"}

    assert repair(repo, noisy).autocrlf is None
    assert _autocrlf(repo) == "false"  # _init_lf_repo set it; the rollback put it back
