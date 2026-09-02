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


def _settings(min_modified_age: float | None = None) -> Settings:
    """Settings carrying only the threshold the skip reason still reads.

    Mutes and visits are applied a level earlier, at the walk (``mute_store.ScanSkip``), so
    ``min_visit_age`` no longer reaches this predicate at all.
    """
    return Settings(folders=(Path("."),), min_modified_age=min_modified_age)


def test_recently_changed_repo_reports_its_age() -> None:
    reason = main.build_skip_reason(_settings(min_modified_age=3600.0))(_status(_NOW - 300.0))
    assert reason == "changed 5 minutes ago"


def test_old_enough_repo_has_no_skip_reason() -> None:
    assert (
        main.build_skip_reason(_settings(min_modified_age=3600.0))(_status(_NOW - 7200.0)) is None
    )


def test_undated_repo_has_no_skip_reason() -> None:
    # latest_change stays 0.0 when no changed file had a readable mtime -- not "1970".
    assert main.build_skip_reason(_settings(min_modified_age=3600.0))(_status(0.0)) is None


def test_no_threshold_means_actionable() -> None:
    assert main.build_skip_reason(_settings())(_status(_NOW)) is None


def _run_commit_ask(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *extra: str
) -> dict[str, object]:
    """Run main in --commit-ask with the scan and the menu stubbed; return what it passed on."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text('{"folders": ["."], "commit_command": "echo hi"}', encoding="utf-8")
    seen: dict[str, object] = {}

    def fake_report(
        statuses: object, limit: object = None, skip_reason: object = None
    ) -> list[RepoStatus]:
        seen["skip_reason"] = skip_reason
        return []

    def fake_scan_all(settings: object, **kwargs: object) -> list[RepoStatus]:
        seen.update(kwargs)
        return []

    monkeypatch.setattr(main, "scan_all", fake_scan_all)
    monkeypatch.setattr(main, "report", fake_report)
    monkeypatch.setattr(main, "commit_interactive", lambda *args, **kwargs: None)
    assert main.main(["--settings", str(settings_file), "--commit-ask", *extra]) == 0
    return seen


def test_commit_ask_filters_the_walk_itself(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Muted and recently-seen repos must cost no git call, not merely be labelled."""
    seen = _run_commit_ask(monkeypatch, tmp_path)
    assert callable(seen["skip"])
    assert callable(seen["on_clean"])
    assert callable(seen["skip_reason"])


def test_all_flag_drops_the_walk_filter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--all must leave --commit-ask unfiltered, so muted repos get scanned and prompted too."""
    seen = _run_commit_ask(monkeypatch, tmp_path, "--all")
    assert seen["skip"] is None
    assert seen["skip_reason"] is None
    # Still recorded: a repo checked under --all was checked all the same.
    assert callable(seen["on_clean"])


def test_checked_repo_is_recorded_by_the_walk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, store: MuteStore
) -> None:
    monkeypatch.setattr(main, "MuteStore", lambda *_a, **_k: store)
    on_clean = _run_commit_ask(monkeypatch, tmp_path)["on_clean"]
    assert callable(on_clean)
    on_clean(Path("repo0"))
    assert store.last_visit(_REPO) == _NOW
