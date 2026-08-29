"""Unit tests for scanner parsing logic — no real git, subprocess is mocked."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import scanner
from git_repo_status_check.constants import GIT_DIR, MODIFIED_ONLY_CODES


def _fake_completed(
    stdout: str, returncode: int = 0, stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


def _stub_git(
    monkeypatch: pytest.MonkeyPatch,
    porcelain: str,
    *,
    real: list[str] | None = None,
    returncode: int = 0,
    stderr: str = "",
    diff_returncode: int = 0,
) -> None:
    """Answer ``git status --porcelain`` with ``porcelain``, the ignore-CR diffs with ``real``.

    ``real`` defaults to every modified path in ``porcelain`` — nothing is line-ending noise,
    which is what every test that does not exercise the filter expects.
    """
    if real is None:
        real = [
            scanner._porcelain_path(line)
            for line in porcelain.splitlines()
            if line[:2] in MODIFIED_ONLY_CODES
        ]
    diff_out = "".join(f"{path}\n" for path in real)

    def run(command: tuple[str, ...], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if "diff" in command:
            return _fake_completed(diff_out, diff_returncode)
        return _fake_completed(porcelain, returncode, stderr)

    monkeypatch.setattr(subprocess, "run", run)


def test_dirty_info_counts_nonblank_porcelain_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("file_a.py", "file_b.py", "file_c.py"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    porcelain = " M file_a.py\n?? file_b.py\nA  file_c.py\n"
    _stub_git(monkeypatch, porcelain)
    count, latest = scanner.dirty_info(tmp_path)
    assert count == 3
    assert latest == pytest.approx((tmp_path / "file_c.py").stat().st_mtime)


def test_dirty_info_clean_repo_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, "")
    assert scanner.dirty_info(Path("repo")) == (0, 0.0)


def test_dirty_info_returns_zero_on_git_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, "", returncode=128)
    assert scanner.dirty_info(Path("repo")) == (0, 0.0)


def test_run_git_not_a_repo_warns_cleanly(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # .git exists but is broken (dead gitlink/worktree) -> git prints a fatal. The repo
    # is still skipped, but the warning must be clean, not the raw fatal stderr.
    stderr = "fatal: not a git repository (or any of the parent directories): .git"
    _stub_git(monkeypatch, "", returncode=128, stderr=stderr)
    with caplog.at_level(logging.WARNING, logger="git_repo_status_check"):
        assert scanner.dirty_info(Path("repo")) == (0, 0.0)
    messages = [r.getMessage() for r in caplog.records]
    assert any("not a valid git repository" in m for m in messages)
    assert not any("fatal:" in m for m in messages)


def test_dirty_info_uses_newest_mtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = tmp_path / "old.py"
    new = tmp_path / "new.py"
    old.write_text("x", encoding="utf-8")
    new.write_text("x", encoding="utf-8")
    os.utime(old, (1000, 1000))
    os.utime(new, (2000, 2000))
    _stub_git(monkeypatch, " M old.py\n M new.py\n")
    _, latest = scanner.dirty_info(tmp_path)
    assert latest == pytest.approx(2000.0)


def test_porcelain_path_resolves_rename_arrow() -> None:
    assert scanner._porcelain_path("R  old_name.py -> new_name.py") == "new_name.py"


def test_changed_file_ages_returns_path_and_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "here.py").write_text("x", encoding="utf-8")
    porcelain = " M here.py\n D gone.py\n"
    _stub_git(monkeypatch, porcelain)
    files = scanner.changed_file_ages(tmp_path)
    assert [f.path for f in files] == ["here.py", "gone.py"]
    assert files[0].mtime == pytest.approx((tmp_path / "here.py").stat().st_mtime)
    assert files[1].mtime is None  # deleted file -> no mtime


def test_changed_file_ages_empty_on_git_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, "", returncode=128)
    assert scanner.changed_file_ages(Path("repo")) == []


def test_dirty_info_skips_deleted_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A deleted file has no mtime; count still includes it, latest stays 0.
    _stub_git(monkeypatch, " D gone.py\n")
    assert scanner.dirty_info(tmp_path) == (1, 0.0)


def test_line_ending_only_changes_make_repo_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # LF blobs checked out as CRLF: git calls them modified, --ignore-cr-at-eol says otherwise.
    for name in ("a.py", "b.py"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    _stub_git(monkeypatch, " M a.py\nM  b.py\n", real=[])
    assert scanner.dirty_info(tmp_path) == (0, 0.0)


def test_line_ending_noise_dropped_but_real_changes_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    noise = tmp_path / "noise.py"
    real = tmp_path / "real.py"
    noise.write_text("x", encoding="utf-8")
    real.write_text("x", encoding="utf-8")
    os.utime(noise, (5000, 5000))
    os.utime(real, (1000, 1000))
    _stub_git(monkeypatch, " M noise.py\n M real.py\n", real=["real.py"])
    files = scanner.changed_file_ages(tmp_path)
    assert [f.path for f in files] == ["real.py"]
    # The dropped file was the newest one -- its mtime must not leak into the repo's age.
    assert scanner.dirty_info(tmp_path) == (1, pytest.approx(1000.0))


@pytest.mark.parametrize("porcelain", ["?? new.py\n", " D gone.py\n", "R  old.py -> new.py\n"])
def test_non_modification_entries_are_never_filtered(
    porcelain: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_git(monkeypatch, porcelain, real=[])
    assert len(scanner.changed_file_ages(tmp_path)) == 1


def test_quoted_path_is_never_filtered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # git quotes non-ASCII paths in porcelain but escapes them differently in diff --name-only,
    # so they cannot be matched and must be kept.
    _stub_git(monkeypatch, ' M "\\303\\274ber.py"\n', real=[])
    assert len(scanner.changed_file_ages(tmp_path)) == 1


def test_diff_failure_keeps_every_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A failed diff must not read as "everything was line-ending noise".
    _stub_git(monkeypatch, " M a.py\n M b.py\n", real=[], diff_returncode=128)
    assert len(scanner.changed_file_ages(tmp_path)) == 2


def test_untracked_only_repo_skips_the_diff_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(tuple(command))
        return _fake_completed("?? new.py\n")

    monkeypatch.setattr(subprocess, "run", run)
    assert len(scanner.changed_file_ages(tmp_path)) == 1
    assert len(calls) == 1


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


def test_find_repos_skips_ignore_prefixes(tmp_path: Path) -> None:
    (tmp_path / "_old_foo" / GIT_DIR).mkdir(parents=True)
    (tmp_path / "real" / GIT_DIR).mkdir(parents=True)
    found = list(scanner.find_repos(tmp_path, ("_old_",)))
    assert found == [tmp_path / "real"]


def test_find_repos_default_keeps_prefixed_dirs(tmp_path: Path) -> None:
    (tmp_path / "_old_foo" / GIT_DIR).mkdir(parents=True)
    found = list(scanner.find_repos(tmp_path))
    assert found == [tmp_path / "_old_foo"]
