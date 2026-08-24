"""Unit tests for reporter output: limit slicing, summary, progress TTY guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo_status_check import reporter
from git_repo_status_check.models import RepoStatus


def _statuses(n: int) -> list[RepoStatus]:
    # Newest-first order (as scan_all returns): decreasing latest_change.
    return [
        RepoStatus(path=Path(f"repo{i}"), dirty_count=i + 1, latest_change=float(n - i))
        for i in range(n)
    ]


def test_report_without_limit_shows_all(capsys: pytest.CaptureFixture[str]) -> None:
    reporter.report(_statuses(3))
    out = capsys.readouterr().out
    assert out.count("uncommitted") == 3
    assert "Summary: 3 dirty repo(s)" in out
    assert "(showing" not in out


def test_report_with_limit_slices_and_notes(capsys: pytest.CaptureFixture[str]) -> None:
    reporter.report(_statuses(5), limit=2)
    out = capsys.readouterr().out
    assert out.count("uncommitted") == 2
    assert "repo0" in out and "repo1" in out  # newest-first: first two rows
    assert "repo4" not in out
    assert "Summary: 5 dirty repo(s) (showing 2)" in out


def test_report_limit_larger_than_list_has_no_suffix(capsys: pytest.CaptureFixture[str]) -> None:
    reporter.report(_statuses(2), limit=10)
    out = capsys.readouterr().out
    assert "(showing" not in out


def test_progress_noops_when_not_tty(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)
    reporter.progress(Path("some/repo"))
    reporter.clear_progress()
    assert capsys.readouterr().err == ""


def test_progress_writes_to_stderr_when_tty(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    reporter.progress(Path("some/repo"))
    err = capsys.readouterr().err
    assert "Scanning:" in err and "some" in err
