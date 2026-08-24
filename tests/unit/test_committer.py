"""Unit tests for the interactive commit prompt loop."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import committer
from git_repo_status_check.models import RepoStatus


def _statuses(n: int) -> list[RepoStatus]:
    return [RepoStatus(path=Path(f"repo{i}"), dirty_count=1) for i in range(n)]


def _answers(monkeypatch: pytest.MonkeyPatch, *choices: str) -> None:
    """Feed the given c/s/a choices to input() in order."""
    it = iter(choices)
    monkeypatch.setattr("builtins.input", lambda _: next(it))


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
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock
) -> None:
    _answers(monkeypatch, "c")
    committer.commit_interactive(_statuses(1), "do-commit")

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == "do-commit"
    assert kwargs["shell"] is True
    assert kwargs["cwd"] == str(Path("repo0"))


def test_skip_does_not_run_command(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock
) -> None:
    _answers(monkeypatch, "s")
    committer.commit_interactive(_statuses(1), "do-commit")
    mock_run.assert_not_called()


def test_abort_stops_before_later_repos(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock
) -> None:
    # 'c' would fire on repo1 if abort didn't stop the loop first.
    _answers(monkeypatch, "a", "c")
    committer.commit_interactive(_statuses(2), "do-commit")
    mock_run.assert_not_called()


def test_invalid_input_reprompts(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock
) -> None:
    _answers(monkeypatch, "x", "", "c")
    committer.commit_interactive(_statuses(1), "do-commit")
    mock_run.assert_called_once()


def test_non_tty_returns_without_prompting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    def _fail(_: str) -> str:  # input must never be called without a TTY
        raise AssertionError("input() called without a TTY")

    monkeypatch.setattr("builtins.input", _fail)
    run = MagicMock()
    monkeypatch.setattr(committer.subprocess, "run", run)

    committer.commit_interactive(_statuses(1), "do-commit")
    run.assert_not_called()
