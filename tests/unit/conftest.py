"""Shared unit-test fixtures."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import repo_actions
from git_repo_status_check.mute_store import MuteStore, PullMute, PushMute, PushVisit


@pytest.fixture
def store(tmp_path: Path) -> MuteStore:
    return MuteStore(tmp_path / "mutes.db")


@pytest.fixture
def pull_store(tmp_path: Path) -> MuteStore:
    """The same database, addressing the ``--pull-ask`` mute table instead."""
    return MuteStore(tmp_path / "mutes.db", PullMute)


@pytest.fixture
def push_store(tmp_path: Path) -> MuteStore:
    """The same database, addressing the ``--push-ask`` tables."""
    return MuteStore(tmp_path / "mutes.db", PushMute, PushVisit)


@pytest.fixture
def mock_run(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Interactive TTY + a stubbed subprocess.run returning success.

    The pull's line-ending check would otherwise read the same stub as git output; it is
    answered here with "no noise" so the stub only sees the commands the tests count.
    """
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = 0
    run = MagicMock(return_value=result)
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(repo_actions, "line_ending_only_paths", lambda _repo: set())
    return run


@pytest.fixture
def mock_popen(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Stubbed subprocess.Popen — the fire-and-forget launcher used for the file explorer."""
    popen = MagicMock(return_value=MagicMock(spec=subprocess.Popen))
    monkeypatch.setattr(subprocess, "Popen", popen)
    return popen
