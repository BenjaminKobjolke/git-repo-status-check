"""Unit tests for the interactive commit prompt loop."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import committer
from git_repo_status_check.constants import AGE_DATE_FORMAT
from git_repo_status_check.models import ChangedFile, RepoStatus
from git_repo_status_check.mute_store import MuteStore


def _statuses(n: int) -> list[RepoStatus]:
    return [RepoStatus(path=Path(f"repo{i}"), dirty_count=1) for i in range(n)]


def _answers(monkeypatch: pytest.MonkeyPatch, *choices: str) -> None:
    """Feed the given menu choices to input() in order."""
    it = iter(choices)
    monkeypatch.setattr("builtins.input", lambda _: next(it))


@pytest.fixture
def store(tmp_path: Path) -> MuteStore:
    return MuteStore(tmp_path / "mutes.db")


@pytest.fixture
def mock_run(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Interactive TTY + a stubbed subprocess.run returning success."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = 0
    run = MagicMock(return_value=result)
    monkeypatch.setattr(committer.subprocess, "run", run)
    return run


def test_commit_runs_command_in_repo_dir(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    _answers(monkeypatch, "c")
    committer.commit_interactive(_statuses(1), "do-commit", store)

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == "do-commit"
    assert kwargs["shell"] is True
    assert kwargs["cwd"] == str(Path("repo0"))


def test_skip_does_not_run_command(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    _answers(monkeypatch, "s")
    committer.commit_interactive(_statuses(1), "do-commit", store)
    mock_run.assert_not_called()


def test_abort_stops_before_later_repos(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    # 'c' would fire on repo1 if abort didn't stop the loop first.
    _answers(monkeypatch, "a", "c")
    committer.commit_interactive(_statuses(2), "do-commit", store)
    mock_run.assert_not_called()


def test_invalid_input_reprompts(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    _answers(monkeypatch, "x", "", "c")
    committer.commit_interactive(_statuses(1), "do-commit", store)
    mock_run.assert_called_once()


def test_list_files_reprompts_and_prints_changes(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(committer, "_run_git", lambda p, a: " M foo.py\n?? bar.txt\n")
    _answers(monkeypatch, "m", "l", "b", "c")  # more -> list -> back -> commit
    committer.commit_interactive(_statuses(1), "do-commit", store)

    out = capsys.readouterr().out
    assert "foo.py" in out and "bar.txt" in out
    mock_run.assert_called_once()  # 'l' did not consume the repo


def test_pull_runs_git_pull_and_reprompts(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    _answers(monkeypatch, "m", "p", "b", "c")  # more -> pull -> back -> commit
    committer.commit_interactive(_statuses(1), "do-commit", store)

    # subprocess.run fires twice: once for the pull, once for the commit command.
    assert mock_run.call_count == 2
    pull_args = mock_run.call_args_list[0].args[0]
    assert tuple(pull_args) == ("git", "-C", str(Path("repo0")), "pull")


def test_more_back_returns_to_top(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    _answers(monkeypatch, "m", "b", "c")  # more -> back -> commit the same repo
    committer.commit_interactive(_statuses(1), "do-commit", store)
    mock_run.assert_called_once()


def test_list_ages_groups_when_all_files_share_one_date(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    files = [ChangedFile(path="foo.py", mtime=1000.0), ChangedFile(path="bar.txt", mtime=2000.0)]
    monkeypatch.setattr(committer, "changed_file_ages", lambda p: files)
    same_day = datetime.fromtimestamp(1000.0).strftime(AGE_DATE_FORMAT)
    _answers(monkeypatch, "m", "a", "b", "s")  # more -> age -> back -> skip
    committer.commit_interactive(_statuses(1), "do-commit", store)

    out = capsys.readouterr().out
    assert f"All 2 files: {same_day}" in out


def test_list_ages_lists_per_file_on_multiple_dates(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    early, late = 0.0, 40.0 * 86400.0  # ~40 days apart -> different DD.MM.YYYY
    files = [ChangedFile(path="foo.py", mtime=early), ChangedFile(path="bar.txt", mtime=late)]
    monkeypatch.setattr(committer, "changed_file_ages", lambda p: files)
    _answers(monkeypatch, "m", "a", "b", "s")
    committer.commit_interactive(_statuses(1), "do-commit", store)

    out = capsys.readouterr().out
    assert datetime.fromtimestamp(early).strftime(AGE_DATE_FORMAT) in out
    assert datetime.fromtimestamp(late).strftime(AGE_DATE_FORMAT) in out
    assert "All " not in out  # not grouped


def test_list_ages_does_not_group_when_some_files_undated(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    files = [ChangedFile(path="foo.py", mtime=1000.0), ChangedFile(path="gone.py", mtime=None)]
    monkeypatch.setattr(committer, "changed_file_ages", lambda p: files)
    _answers(monkeypatch, "m", "a", "b", "s")
    committer.commit_interactive(_statuses(1), "do-commit", store)

    out = capsys.readouterr().out
    assert "All " not in out  # one file is undated -> no grouped total
    assert "foo.py" in out


def test_list_ages_reports_no_dated_files(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(committer, "changed_file_ages", lambda p: [ChangedFile("gone.py", None)])
    _answers(monkeypatch, "m", "a", "b", "s")
    committer.commit_interactive(_statuses(1), "do-commit", store)

    out = capsys.readouterr().out
    assert "(no dated files)" in out


def test_non_tty_returns_without_prompting(
    monkeypatch: pytest.MonkeyPatch, store: MuteStore
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    def _fail(_: str) -> str:  # input must never be called without a TTY
        raise AssertionError("input() called without a TTY")

    monkeypatch.setattr("builtins.input", _fail)
    run = MagicMock()
    monkeypatch.setattr(committer.subprocess, "run", run)

    committer.commit_interactive(_statuses(1), "do-commit", store)
    run.assert_not_called()


def test_mute_stores_timeframe_and_skips_commit(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    monkeypatch.setattr(committer.time, "time", lambda: 1000.0)
    _answers(monkeypatch, "m", "m", "1w")  # more -> mute -> one week
    committer.commit_interactive(_statuses(1), "do-commit", store)

    mock_run.assert_not_called()  # muting does not commit
    assert store.is_muted(str(Path("repo0")), now=1000.0) is True
    assert store.is_muted(str(Path("repo0")), now=1000.0 + 604800.0) is False


def test_mute_reprompts_on_invalid_timeframe(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    monkeypatch.setattr(committer.time, "time", lambda: 0.0)
    _answers(monkeypatch, "m", "m", "nope", "1d")  # more -> mute -> bad, then good
    committer.commit_interactive(_statuses(1), "do-commit", store)
    assert store.is_muted(str(Path("repo0")), now=0.0) is True


def test_already_muted_repo_is_skipped_silently(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    monkeypatch.setattr(committer.time, "time", lambda: 0.0)
    store.mute(str(Path("repo0")), muted_until=500.0)

    def _fail(_: str) -> str:  # a muted repo must not be prompted
        raise AssertionError("input() called for a muted repo")

    monkeypatch.setattr("builtins.input", _fail)
    committer.commit_interactive(_statuses(1), "do-commit", store)
    mock_run.assert_not_called()


def _fresh_status(latest_change: float) -> list[RepoStatus]:
    return [RepoStatus(path=Path("repo0"), dirty_count=1, latest_change=latest_change)]


def test_recently_changed_repo_is_skipped_silently(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    monkeypatch.setattr(committer.time, "time", lambda: 10_000.0)

    def _fail(_: str) -> str:  # a too-fresh repo must not be prompted
        raise AssertionError("input() called for a too-fresh repo")

    monkeypatch.setattr("builtins.input", _fail)
    committer.commit_interactive(
        _fresh_status(10_000.0 - 60.0), "do-commit", store, min_modified_age=3600.0
    )
    mock_run.assert_not_called()


def test_old_enough_repo_is_still_prompted(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    monkeypatch.setattr(committer.time, "time", lambda: 10_000.0)
    _answers(monkeypatch, "c")
    committer.commit_interactive(
        _fresh_status(10_000.0 - 7200.0), "do-commit", store, min_modified_age=3600.0
    )
    mock_run.assert_called_once()


def test_undated_repo_is_prompted_despite_threshold(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    # latest_change stays 0.0 when no changed file had a readable mtime -- not "1970".
    monkeypatch.setattr(committer.time, "time", lambda: 10_000.0)
    _answers(monkeypatch, "c")
    committer.commit_interactive(_fresh_status(0.0), "do-commit", store, min_modified_age=3600.0)
    mock_run.assert_called_once()
