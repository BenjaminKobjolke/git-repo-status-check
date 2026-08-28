"""Shared unit-test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo_status_check.mute_store import MuteStore


@pytest.fixture
def store(tmp_path: Path) -> MuteStore:
    return MuteStore(tmp_path / "mutes.db")
