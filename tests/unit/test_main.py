"""Unit tests for the --commit-ask skip-reason callback built in main."""

from __future__ import annotations

from pathlib import Path

import pytest

import main
from git_repo_status_check.models import RepoStatus
from git_repo_status_check.mute_store import MuteStore
from git_repo_status_check.settings import Settings

_NOW = 10_000.0
_REPO = str(Path("repo0"))


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.time", lambda: _NOW)


def _status(latest_change: float = 0.0) -> RepoStatus:
    return RepoStatus(path=Path("repo0"), dirty_count=1, latest_change=latest_change)


def _settings(
    min_modified_age: float | None = None, min_visit_age: float | None = None
) -> Settings:
    """Settings carrying only the two thresholds the skip reason reads."""
    return Settings(
        folders=(Path("."),),
        min_modified_age=min_modified_age,
        min_visit_age=min_visit_age,
    )


def test_muted_repo_reports_remaining_time(store: MuteStore) -> None:
    store.mute(_REPO, muted_until=_NOW + 2 * 86400.0)
    assert main.build_skip_reason(store, _settings())(_status()) == "muted for 2 days"


def test_recently_changed_repo_reports_its_age(store: MuteStore) -> None:
    reason = main.build_skip_reason(store, _settings(min_modified_age=3600.0))(
        _status(_NOW - 300.0)
    )
    assert reason == "changed 5 minutes ago"


def test_old_enough_repo_has_no_skip_reason(store: MuteStore) -> None:
    settings = _settings(min_modified_age=3600.0)
    assert main.build_skip_reason(store, settings)(_status(_NOW - 7200.0)) is None


def test_undated_repo_has_no_skip_reason(store: MuteStore) -> None:
    # latest_change stays 0.0 when no changed file had a readable mtime -- not "1970".
    settings = _settings(min_modified_age=3600.0)
    assert main.build_skip_reason(store, settings)(_status(0.0)) is None


def test_no_threshold_and_no_mute_means_actionable(store: MuteStore) -> None:
    assert main.build_skip_reason(store, _settings())(_status(_NOW)) is None


def test_recently_visited_repo_reports_how_long_ago(store: MuteStore) -> None:
    store.record_visit(_REPO, visited_at=_NOW - 600.0)
    settings = _settings(min_visit_age=3600.0)
    assert main.build_skip_reason(store, settings)(_status()) == "seen 10 minutes ago"


def test_visit_older_than_the_window_is_actionable_again(store: MuteStore) -> None:
    store.record_visit(_REPO, visited_at=_NOW - 7200.0)
    settings = _settings(min_visit_age=3600.0)
    assert main.build_skip_reason(store, settings)(_status()) is None


def test_visit_is_ignored_when_min_visit_age_is_off(store: MuteStore) -> None:
    store.record_visit(_REPO, visited_at=_NOW)
    assert main.build_skip_reason(store, _settings(min_visit_age=None))(_status()) is None


def test_mute_wins_over_a_fresh_visit(store: MuteStore) -> None:
    """An explicit mute is the user's own decision, so its label takes precedence."""
    store.mute(_REPO, muted_until=_NOW + 2 * 86400.0)
    store.record_visit(_REPO, visited_at=_NOW)
    settings = _settings(min_visit_age=3600.0)
    assert main.build_skip_reason(store, settings)(_status()) == "muted for 2 days"


def test_visit_wins_over_a_recent_change(store: MuteStore) -> None:
    """Both apply; the visit is checked first so the label names what you actually did."""
    store.record_visit(_REPO, visited_at=_NOW - 600.0)
    settings = _settings(min_modified_age=3600.0, min_visit_age=3600.0)
    assert main.build_skip_reason(store, settings)(_status(_NOW - 60.0)) == "seen 10 minutes ago"
