"""Unit tests for the commit menu's rename action (r): prefix the repo folder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import committer
from git_repo_status_check.constants import RENAME_PREFIX_NOT_CONFIGURED
from git_repo_status_check.models import RepoStatus
from git_repo_status_check.mute_store import MuteStore

from .helpers import _answers


def _repo_status(path: Path) -> list[RepoStatus]:
    return [RepoStatus(path=path, dirty_count=1)]


def test_rename_prefixes_folder_and_skips_commit(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore, tmp_path: Path
) -> None:
    repo = tmp_path / "project"
    repo.mkdir()
    _answers(monkeypatch, "m", "r")  # more -> rename; the repo is consumed
    committer.commit_interactive(_repo_status(repo), "do-commit", store, rename_prefix="_old_")

    assert not repo.exists()
    assert (tmp_path / "_old_project").is_dir()
    mock_run.assert_not_called()  # renaming does not commit


def test_rename_without_setting_reports_and_reprompts(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = tmp_path / "project"
    repo.mkdir()
    _answers(monkeypatch, "m", "r", "b", "c")  # more -> rename -> back -> commit
    committer.commit_interactive(_repo_status(repo), "do-commit", store)

    assert RENAME_PREFIX_NOT_CONFIGURED.strip() in capsys.readouterr().out
    assert repo.is_dir()
    mock_run.assert_called_once()  # 'r' did not consume the repo


def test_rename_refuses_when_target_exists(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = tmp_path / "project"
    repo.mkdir()
    (tmp_path / "_old_project").mkdir()
    _answers(monkeypatch, "m", "r", "b", "s")  # rename fails -> back -> skip
    committer.commit_interactive(_repo_status(repo), "do-commit", store, rename_prefix="_old_")

    assert "already exists" in capsys.readouterr().out
    assert repo.is_dir()


def test_rename_refuses_when_already_prefixed(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = tmp_path / "_old_project"
    repo.mkdir()
    _answers(monkeypatch, "m", "r", "b", "s")
    committer.commit_interactive(_repo_status(repo), "do-commit", store, rename_prefix="_old_")

    assert "Already prefixed" in capsys.readouterr().out
    assert repo.is_dir()
