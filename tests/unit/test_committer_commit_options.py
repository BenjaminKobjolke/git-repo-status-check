"""Typed-message and TortoiseGit options in the commit menu."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import committer
from git_repo_status_check.constants import COMMIT_MENU
from git_repo_status_check.mute_store import MuteStore

from .helpers import _ahead, _answers, _statuses


def test_typed_message_commits_then_pushes_without_shell(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    monkeypatch.setattr(committer, "measure_ahead", lambda _path: _ahead("repo0"))
    _answers(monkeypatch, "t", '  fix "typo" & go  ')

    assert committer.commit_interactive(_statuses(1), None, store)

    assert [call.args[0] for call in mock_run.call_args_list] == [
        ("git", "-C", "repo0", "add", "-A"),
        ("git", "-C", "repo0", "commit", "-m", 'fix "typo" & go'),
        ("git", "-C", "repo0", "push"),
    ]
    assert all(call.kwargs.get("shell", False) is False for call in mock_run.call_args_list)


def test_typed_message_sets_upstream_when_needed(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    monkeypatch.setattr(committer, "measure_ahead", lambda _path: _ahead("repo0", upstream=None))
    _answers(monkeypatch, "t", "message")
    committer.commit_interactive(_statuses(1), None, store)
    assert tuple(mock_run.call_args_list[-1].args[0]) == (
        "git", "-C", "repo0", "push", "-u", "origin", "main"
    )


def test_empty_message_reprompts_same_repo_and_records_one_visit(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _answers(monkeypatch, "t", "   ", "s")
    assert committer.commit_interactive(_statuses(1), None, store)
    mock_run.assert_not_called()
    assert "Empty commit message" in capsys.readouterr().out
    assert store.last_visit("repo0") is not None


def test_failed_commit_reprompts_without_push(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    mock_run.side_effect = [MagicMock(returncode=0), MagicMock(returncode=1)]
    _answers(monkeypatch, "t", "message", "s")
    assert committer.commit_interactive(_statuses(1), None, store)
    assert mock_run.call_count == 2


def test_no_push_target_leaves_local_commit(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    monkeypatch.setattr(committer, "measure_ahead", lambda _path: None)
    _answers(monkeypatch, "t", "message")
    assert committer.commit_interactive(_statuses(1), None, store)
    assert mock_run.call_count == 2


def test_failed_push_continues_to_next_repo(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    monkeypatch.setattr(committer, "measure_ahead", lambda path: _ahead(str(path)))
    mock_run.side_effect = [
        MagicMock(returncode=0),
        MagicMock(returncode=0),
        MagicMock(returncode=1),
        MagicMock(returncode=0),
        MagicMock(returncode=0),
        MagicMock(returncode=0),
    ]
    _answers(monkeypatch, "t", "first", "t", "second")
    assert committer.commit_interactive(_statuses(2), None, store)
    assert any("repo1" in call.args[0] for call in mock_run.call_args_list)


def test_tortoisegit_path_is_one_argument_without_shell(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    status = _statuses(1)[0]
    status = status.__class__(path=Path("repo space & more"), dirty_count=1)
    monkeypatch.setattr(committer.menu, "choose", lambda _items, _title: "g")
    assert committer.commit_interactive([status], None, store)
    mock_run.assert_called_once_with(
        ("TortoiseGitProc.exe", "/command:commit", "/path:repo space & more"),
        shell=False,
        cwd="repo space & more",
        check=False,
    )


@pytest.mark.parametrize("command", [None, "do-commit"])
def test_menu_hides_only_configured_command(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore, command: str | None
) -> None:
    def choose(items, _title):
        mock_run.items = items
        return "s"

    monkeypatch.setattr(committer.menu, "choose", choose)
    committer.commit_interactive(_statuses(1), command, store)
    items = mock_run.items
    assert (items == COMMIT_MENU) is bool(command)
    if command is None:
        assert {choice for _, choice in items} >= {"t", "g"}
        assert "c" not in {choice for _, choice in items}
