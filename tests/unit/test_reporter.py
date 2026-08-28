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


def test_report_returns_shown_list_unlimited() -> None:
    statuses = _statuses(3)
    assert reporter.report(statuses) == statuses


def test_report_returns_shown_list_when_limited() -> None:
    statuses = _statuses(5)
    assert reporter.report(statuses, limit=2) == statuses[:2]


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


def _skip_first_three(status: RepoStatus) -> str | None:
    return "muted for 2 days" if status.path.name in ("repo0", "repo1", "repo2") else None


def test_skipped_rows_print_labelled_but_do_not_consume_the_limit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    statuses = _statuses(6)
    shown = reporter.report(statuses, limit=2, skip_reason=_skip_first_three)

    out = capsys.readouterr().out
    assert out.count("muted for 2 days") == 3  # repo0..repo2 listed, labelled
    assert "repo3" in out and "repo4" in out  # the two actionable rows
    assert "repo5" not in out  # limit reached, walk stopped
    assert shown == [statuses[3], statuses[4]]  # only actionable rows are returned
    assert "Summary: 6 dirty repo(s) (showing 2)" in out


def test_skip_reason_without_limit_shows_everything(capsys: pytest.CaptureFixture[str]) -> None:
    statuses = _statuses(4)
    shown = reporter.report(statuses, skip_reason=_skip_first_three)

    out = capsys.readouterr().out
    assert out.count("uncommitted") == 4
    assert "(showing" not in out
    assert shown == [statuses[3]]


def test_summary_suffix_counts_repos_not_submodules(capsys: pytest.CaptureFixture[str]) -> None:
    statuses = [
        RepoStatus(path=Path("repo0"), dirty_count=1),
        RepoStatus(path=Path("repo0/sub"), dirty_count=1, is_submodule=True),
        RepoStatus(path=Path("repo1"), dirty_count=1),
    ]
    reporter.report(statuses, limit=1)
    assert "Summary: 2 dirty repo(s) (showing 1)" in capsys.readouterr().out
