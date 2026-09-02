"""Shared unit-test fixtures."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import committer
from git_repo_status_check.mute_store import MuteStore, PullMute


@pytest.fixture
def store(tmp_path: Path) -> MuteStore:
    return MuteStore(tmp_path / "mutes.db")


@pytest.fixture
def pull_store(tmp_path: Path) -> MuteStore:
    """The same database, addressing the ``--pull-ask`` mute table instead."""
    return MuteStore(tmp_path / "mutes.db", PullMute)


@pytest.fixture
def mock_run(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Interactive TTY + a stubbed subprocess.run returning success."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = 0
    run = MagicMock(return_value=result)
    monkeypatch.setattr(committer.subprocess, "run", run)
    return run


@pytest.fixture
def mock_popen(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Stubbed subprocess.Popen — the fire-and-forget launcher used for the file explorer."""
    popen = MagicMock(return_value=MagicMock(spec=subprocess.Popen))
    monkeypatch.setattr(committer.subprocess, "Popen", popen)
    return popen
