"""Unit tests for the --commit-ask skip-reason callback built in main."""

from __future__ import annotations

from pathlib import Path

import pytest

import main
from git_repo_status_check.models import RepoStatus
from git_repo_status_check.mute_store import MuteStore

_NOW = 10_000.0


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.time", lambda: _NOW)


def _status(latest_change: float = 0.0) -> RepoStatus:
    return RepoStatus(path=Path("repo0"), dirty_count=1, latest_change=latest_change)


def test_muted_repo_reports_remaining_time(store: MuteStore) -> None:
    store.mute(str(Path("repo0")), muted_until=_NOW + 2 * 86400.0)
    assert main.build_skip_reason(store, None)(_status()) == "muted for 2 days"


def test_recently_changed_repo_reports_its_age(store: MuteStore) -> None:
    reason = main.build_skip_reason(store, 3600.0)(_status(_NOW - 300.0))
    assert reason == "changed 5 minutes ago"


def test_old_enough_repo_has_no_skip_reason(store: MuteStore) -> None:
    assert main.build_skip_reason(store, 3600.0)(_status(_NOW - 7200.0)) is None


def test_undated_repo_has_no_skip_reason(store: MuteStore) -> None:
    # latest_change stays 0.0 when no changed file had a readable mtime -- not "1970".
    assert main.build_skip_reason(store, 3600.0)(_status(0.0)) is None


def test_no_threshold_and_no_mute_means_actionable(store: MuteStore) -> None:
    assert main.build_skip_reason(store, None)(_status(_NOW)) is None
