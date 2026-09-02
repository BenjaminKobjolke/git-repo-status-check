"""Unit tests for the interactive commit prompt loop."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import committer, menu
from git_repo_status_check.constants import (
    EXPLORER_NOT_CONFIGURED,
    NO_REMOTE_CONFIGURED,
    REPO_PATH_TOKEN,
)
from git_repo_status_check.models import ChangedFile
from git_repo_status_check.mute_store import MuteStore

from .helpers import _answers, _statuses


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


def test_list_files_reprompts_and_prints_changes(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Same source as the dirty count, so the listing never shows files the count excluded.
    listed = [
        ChangedFile(path="foo.py", mtime=1000.0, code=" M"),
        ChangedFile(path="bar.txt", mtime=None, code="??"),
    ]
    monkeypatch.setattr(committer, "changed_file_ages", lambda p: listed)
    _answers(monkeypatch, "m", "l", "b", "c")  # more -> list -> back -> commit
    committer.commit_interactive(_statuses(1), "do-commit", store)

    out = capsys.readouterr().out
    assert " M foo.py" in out and "?? bar.txt" in out
    mock_run.assert_called_once()  # 'l' did not consume the repo


def test_pull_runs_git_pull_and_reprompts(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    _answers(monkeypatch, "m", "p", "b", "c")  # more -> pull -> back -> commit
    committer.commit_interactive(_statuses(1), "do-commit", store)

    # subprocess.run fires twice: once for the pull, once for the commit command.
    assert mock_run.call_count == 2
    pull_args = mock_run.call_args_list[0].args[0]
    assert tuple(pull_args) == ("git", "-C", str(Path("repo0")), "pull", "--no-edit")


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
    same_day = committer.format_age_date(1000.0)
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
    assert committer.format_age_date(early) in out
    assert committer.format_age_date(late) in out
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

    def _fail(*_args: object) -> str:  # no menu may open without a TTY
        raise AssertionError("menu.choose() called without a TTY")

    monkeypatch.setattr(menu, "choose", _fail)
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
    assert store.muted_until(str(Path("repo0")), now=1000.0) == 1000.0 + 604800.0


def test_mute_reprompts_on_invalid_timeframe(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    monkeypatch.setattr(committer.time, "time", lambda: 0.0)
    # more -> mute -> custom -> bad text, then custom -> good text
    _answers(monkeypatch, "m", "m", "custom", "nope", "custom", "1d")
    committer.commit_interactive(_statuses(1), "do-commit", store)
    assert store.muted_until(str(Path("repo0")), now=0.0) == 86400.0


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        (f'fman "{REPO_PATH_TOKEN}"', f'fman "{Path("repo0")}"'),  # token substituted
        ("explorer", f'explorer "{Path("repo0")}"'),  # no token: path appended, quoted
    ],
)
def test_explorer_builds_launch_command(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    mock_popen: MagicMock,
    store: MuteStore,
    configured: str,
    expected: str,
) -> None:
    _answers(monkeypatch, "m", "e", "b", "c")  # more -> explorer -> back -> commit
    committer.commit_interactive(_statuses(1), "do-commit", store, file_explorer=configured)

    mock_popen.assert_called_once()
    assert mock_popen.call_args.args[0] == expected
    mock_run.assert_called_once()  # 'e' did not consume the repo


def test_explorer_without_setting_reports_and_continues(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    mock_popen: MagicMock,
    store: MuteStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _answers(monkeypatch, "m", "e", "b", "c")
    committer.commit_interactive(_statuses(1), "do-commit", store)

    assert EXPLORER_NOT_CONFIGURED.strip() in capsys.readouterr().out
    mock_popen.assert_not_called()
    mock_run.assert_called_once()  # the loop carried on


def test_stash_runs_git_stash_and_skips_the_repo(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    _answers(monkeypatch, "m", "s")  # more -> stash; a stashed repo has nothing left to commit
    committer.commit_interactive(_statuses(1), "do-commit", store)

    mock_run.assert_called_once()  # only the stash — the commit command never ran
    args = tuple(mock_run.call_args.args[0])
    assert args[:6] == ("git", "-C", str(Path("repo0")), "stash", "push", "-u")
    assert args[6] == "-m"
    assert args[7].endswith(" GIT REPO STATUS TOOL")
    assert re.fullmatch(r"\d{4}_\d{2}_\d{2}", args[7].split(" ", 1)[0])


def test_failed_stash_reprompts_instead_of_skipping(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    mock_run.return_value.returncode = 1
    _answers(monkeypatch, "m", "s", "b", "c")  # failed stash -> back -> commit anyway
    committer.commit_interactive(_statuses(1), "do-commit", store)
    assert mock_run.call_count == 2  # the failed stash, then the commit command


def test_url_prints_each_remote_once_and_reprompts(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # `git remote -v` lists every remote twice (fetch + push); only one row should be shown.
    monkeypatch.setattr(
        committer,
        "run_git",
        lambda p, args: (
            "origin\thttps://example.com/x.git (fetch)\norigin\thttps://example.com/x.git (push)\n"
        ),
    )
    _answers(monkeypatch, "m", "u", "b", "c")  # more -> url -> back -> commit
    committer.commit_interactive(_statuses(1), "do-commit", store)

    out = capsys.readouterr().out
    assert out.count("https://example.com/x.git") == 1
    assert "origin" in out
    mock_run.assert_called_once()  # 'u' did not consume the repo


def test_url_without_remote_reports_none(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(committer, "run_git", lambda p, args: "")
    _answers(monkeypatch, "m", "u", "b", "s")  # more -> url -> back -> skip
    committer.commit_interactive(_statuses(1), "do-commit", store)

    assert NO_REMOTE_CONFIGURED.strip() in capsys.readouterr().out
    mock_run.assert_not_called()
