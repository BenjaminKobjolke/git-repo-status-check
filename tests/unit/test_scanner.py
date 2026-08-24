"""Unit tests for scanner parsing logic — no real git, subprocess is mocked."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import scanner
from git_repo_status_check.constants import GIT_DIR


def _fake_completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = ""
    proc.returncode = returncode
    return proc


def test_dirty_info_counts_nonblank_porcelain_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("file_a.py", "file_b.py", "file_c.py"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    porcelain = " M file_a.py\n?? file_b.py\nA  file_c.py\n"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _fake_completed(porcelain))
    count, latest = scanner.dirty_info(tmp_path)
    assert count == 3
    assert latest == pytest.approx((tmp_path / "file_c.py").stat().st_mtime)


def test_dirty_info_clean_repo_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _fake_completed(""))
    assert scanner.dirty_info(Path("repo")) == (0, 0.0)


def test_dirty_info_returns_zero_on_git_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _fake_completed("", returncode=128))
    assert scanner.dirty_info(Path("repo")) == (0, 0.0)


def test_dirty_info_uses_newest_mtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = tmp_path / "old.py"
    new = tmp_path / "new.py"
    old.write_text("x", encoding="utf-8")
    new.write_text("x", encoding="utf-8")
    os.utime(old, (1000, 1000))
    os.utime(new, (2000, 2000))
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _fake_completed(" M old.py\n M new.py\n")
    )
    _, latest = scanner.dirty_info(tmp_path)
    assert latest == pytest.approx(2000.0)


def test_porcelain_path_resolves_rename_arrow() -> None:
    assert scanner._porcelain_path("R  old_name.py -> new_name.py") == "new_name.py"


def test_dirty_info_skips_deleted_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A deleted file has no mtime; count still includes it, latest stays 0.
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _fake_completed(" D gone.py\n"))
    assert scanner.dirty_info(tmp_path) == (1, 0.0)


def test_submodule_paths_parses_gitmodules_file(tmp_path: Path) -> None:
    (tmp_path / ".gitmodules").write_text(
        '[submodule "lib"]\n'
        "\tpath = vendor/lib\n"
        "\turl = https://example.com/lib.git\n"
        '[submodule "thing"]\n'
        "\tpath = plugins/thing\n"
        "\turl = https://example.com/thing.git\n",
        encoding="utf-8",
    )
    paths = scanner._submodule_paths(tmp_path)
    assert paths == [tmp_path / "vendor/lib", tmp_path / "plugins/thing"]


def test_submodule_paths_missing_gitmodules_is_empty(tmp_path: Path) -> None:
    assert scanner._submodule_paths(tmp_path) == []


def test_find_repos_stops_descending_into_repo(tmp_path: Path) -> None:
    # root/repo/.git and a nested root/repo/inner/.git that must NOT be reported.
    repo = tmp_path / "repo"
    (repo / GIT_DIR).mkdir(parents=True)
    (repo / "inner" / GIT_DIR).mkdir(parents=True)
    found = list(scanner.find_repos(tmp_path))
    assert found == [repo]


def test_find_repos_skips_noise_dirs(tmp_path: Path) -> None:
    (tmp_path / "node_modules" / "pkg" / GIT_DIR).mkdir(parents=True)
    (tmp_path / "real" / GIT_DIR).mkdir(parents=True)
    found = list(scanner.find_repos(tmp_path))
    assert found == [tmp_path / "real"]
