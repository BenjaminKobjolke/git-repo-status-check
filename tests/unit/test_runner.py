"""Unit tests for the mode orchestration in runner, driven through main's argument parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

import main
from git_repo_status_check import runner
from git_repo_status_check.models import RepoStatus
from git_repo_status_check.mute_store import MuteStore, PushMute, PushVisit
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
    reason = runner.build_skip_reason(_settings(min_modified_age=3600.0))(_status(_NOW - 300.0))
    assert reason == "changed 5 minutes ago"


def test_old_enough_repo_has_no_skip_reason() -> None:
    assert (
        runner.build_skip_reason(_settings(min_modified_age=3600.0))(_status(_NOW - 7200.0)) is None
    )


def test_undated_repo_has_no_skip_reason() -> None:
    # latest_change stays 0.0 when no changed file had a readable mtime -- not "1970".
    assert runner.build_skip_reason(_settings(min_modified_age=3600.0))(_status(0.0)) is None


def test_no_threshold_means_actionable() -> None:
    assert runner.build_skip_reason(_settings())(_status(_NOW)) is None


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

    monkeypatch.setattr(runner, "scan_all", fake_scan_all)
    monkeypatch.setattr(runner, "report", fake_report)
    monkeypatch.setattr(runner, "commit_interactive", lambda *args, **kwargs: None)
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
    monkeypatch.setattr(runner, "MuteStore", lambda *_a, **_k: store)
    on_clean = _run_commit_ask(monkeypatch, tmp_path)["on_clean"]
    assert callable(on_clean)
    on_clean(Path("repo0"))
    assert store.last_visit(_REPO) == _NOW


@pytest.mark.parametrize(("extra", "expected_all"), [((), False), (("--all",), True)])
def test_push_ask_runs_the_push_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, extra: tuple[str, ...], expected_all: bool
) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text('{"folders": ["."]}', encoding="utf-8")
    seen: dict[str, object] = {}

    def fake_push(settings: object, store: object, prompt_all: bool = False) -> None:
        seen["prompt_all"] = prompt_all

    monkeypatch.setattr(runner, "push_interactive", fake_push)
    monkeypatch.setattr(runner, "scan_all", lambda *_a, **_k: pytest.fail("must not scan"))
    assert main.main(["--settings", str(settings_file), "--push-ask", *extra]) == 0
    assert seen["prompt_all"] is expected_all


def test_list_muted_has_a_push_section(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(main, "_PROJECT_ROOT", tmp_path)
    MuteStore(tmp_path / "mutes.db", PushMute, PushVisit).mute("D:/GIT/foo", _NOW + 3600)
    assert main.main(["--list-muted"]) == 0
    out = capsys.readouterr().out
    assert "Push mutes (--push-ask):" in out
    assert "D:/GIT/foo" in out


def _run_sync_ask(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *extra: str,
    pull_result: bool = True,
    commit_result: bool = True,
    commit_command: str = "echo hi",
) -> tuple[int, list[str], dict[str, object]]:
    """Run --sync-ask with every stage stubbed; return (exit code, stage order, kwargs seen)."""
    settings_file = tmp_path / "settings.json"
    command = f', "commit_command": "{commit_command}"' if commit_command else ""
    settings_file.write_text('{"folders": ["."]' + command + "}", encoding="utf-8")
    order: list[str] = []
    seen: dict[str, object] = {}

    def fake_pull(settings: object, store: object, prompt_all: bool = False) -> bool:
        order.append("pull")
        seen["pull_all"] = prompt_all
        return pull_result

    def fake_push(settings: object, store: object, prompt_all: bool = False) -> bool:
        order.append("push")
        seen["push_all"] = prompt_all
        return True

    def fake_commit(*_a: object, **_k: object) -> bool:
        order.append("commit")
        return commit_result

    monkeypatch.setattr(runner, "pull_interactive", fake_pull)
    monkeypatch.setattr(runner, "push_interactive", fake_push)
    monkeypatch.setattr(runner, "scan_all", lambda *_a, **_k: [])
    monkeypatch.setattr(runner, "report", lambda *_a, **_k: [])
    monkeypatch.setattr(runner, "commit_interactive", fake_commit)
    code = main.main(["--settings", str(settings_file), "--sync-ask", *extra])
    return code, order, seen


@pytest.mark.parametrize(("extra", "expected_all"), [((), False), (("--all",), True)])
def test_sync_ask_runs_pull_commit_push_in_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, extra: tuple[str, ...], expected_all: bool
) -> None:
    code, order, seen = _run_sync_ask(monkeypatch, tmp_path, *extra)
    assert code == 0
    assert order == ["pull", "commit", "push"]
    assert seen["pull_all"] is expected_all
    assert seen["push_all"] is expected_all


def test_sync_ask_abort_in_pull_stage_ends_the_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    code, order, _ = _run_sync_ask(monkeypatch, tmp_path, pull_result=False)
    assert code == 0
    assert order == ["pull"]


def test_sync_ask_abort_in_commit_stage_skips_push(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _, order, _ = _run_sync_ask(monkeypatch, tmp_path, commit_result=False)
    assert order == ["pull", "commit"]


def test_sync_ask_requires_commit_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, order, _ = _run_sync_ask(monkeypatch, tmp_path, commit_command="")
    assert code == 1
    assert order == []
    assert "--sync-ask" in capsys.readouterr().err
