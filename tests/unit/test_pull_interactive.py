"""Unit tests for the --pull-ask menu loop: what each answer does, and what it records.

The walk that feeds it is tested in ``test_upstream``; git calls are stubbed throughout, so
nothing here touches a real repo or the network.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from git_repo_status_check import menu, scanner, upstream
from git_repo_status_check.mute_store import MuteStore
from git_repo_status_check.settings import Settings

from .helpers import _behind, _run_pull
from .helpers import _stub_upstream_git as _stub_git


def test_pull_runs_git_pull_for_the_repo(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    assert _run_pull(monkeypatch, pull_store, [_behind("repo0")], "p") == [Path("repo0")]


def test_skip_does_not_pull(monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore) -> None:
    assert _run_pull(monkeypatch, pull_store, [_behind("repo0")], "s") == []


def test_abort_stops_before_the_second_repo(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    # 'p' would fire on repo1 if abort did not stop the loop first.
    assert _run_pull(monkeypatch, pull_store, [_behind("r0"), _behind("r1")], "a", "p") == []


def test_mute_writes_to_the_pull_store(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    monkeypatch.setattr(menu, "ask_timeframe", lambda: 3600.0)
    _run_pull(monkeypatch, pull_store, [_behind("repo0")], "m")
    assert pull_store.muted_until(str(Path("repo0")), 0.0) is not None


def _held_back(
    monkeypatch: pytest.MonkeyPatch,
    store: MuteStore,
    *,
    prompt_all: bool = False,
    min_visit_age: float | None = 3600.0,
    counts: str | None = "1\t0\n",
    upstream_name: str | None = "origin/main",
) -> list[tuple[str, ...]]:
    """Run the whole mode over one repo with git recorded; return the git calls it made.

    An empty list is the assertion that matters throughout: a held-back repo must cost no
    fetch at all, which is the point of filtering before the network rather than after.
    ``counts``/``upstream_name`` also drive the walk over a repo that is *not* behind, which
    is the other way a repo ends up recorded as checked.
    """
    calls = _stub_git(monkeypatch, upstream_name=upstream_name, counts=counts)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(scanner, "find_repos", lambda *_a, **_k: iter([Path("repo0")]))
    monkeypatch.setattr(upstream, "run_pull", lambda _path: True)
    monkeypatch.setattr(menu, "choose", lambda _items, _title: "s")
    monkeypatch.setattr(menu, "pause", lambda: None)
    settings = Settings(folders=(Path("root"),), min_visit_age=min_visit_age)
    upstream.pull_interactive(settings, store, prompt_all=prompt_all)
    return calls


def test_muted_repo_is_never_fetched(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore, capsys: pytest.CaptureFixture[str]
) -> None:
    pull_store.mute(str(Path("repo0")), 2_000_000_000.0)
    assert _held_back(monkeypatch, pull_store) == []
    assert "Skipped 1 repo(s) without fetching" in capsys.readouterr().out


def test_recently_visited_repo_is_never_fetched(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    pull_store.record_visit(str(Path("repo0")), time.time())
    assert _held_back(monkeypatch, pull_store) == []


def test_visit_older_than_min_visit_age_is_fetched(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    pull_store.record_visit(str(Path("repo0")), time.time() - 7200)
    assert _held_back(monkeypatch, pull_store) != []


def test_min_visit_age_of_none_never_holds_a_repo_back(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    pull_store.record_visit(str(Path("repo0")), time.time())
    assert _held_back(monkeypatch, pull_store, min_visit_age=None) != []


def test_prompt_all_fetches_held_back_repos(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    pull_store.mute(str(Path("repo0")), 2_000_000_000.0)
    pull_store.record_visit(str(Path("repo0")), time.time())
    assert _held_back(monkeypatch, pull_store, prompt_all=True) != []


def test_deciding_about_a_repo_records_a_visit(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    _run_pull(monkeypatch, pull_store, [_behind("repo0")], "s")
    assert pull_store.last_visit(str(Path("repo0"))) is not None


def test_abort_still_records_the_repo_you_were_shown(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    """The visit is written before the menu is drawn, so bailing out does not undo it --
    otherwise the same repo greets you on every run."""
    _run_pull(monkeypatch, pull_store, [_behind("repo0")], "a")
    assert pull_store.last_visit(str(Path("repo0"))) is not None


def test_abort_leaves_the_repos_you_never_saw_unrecorded(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    _run_pull(monkeypatch, pull_store, [_behind("r0"), _behind("r1")], "a")
    assert pull_store.last_visit(str(Path("r0"))) is not None
    assert pull_store.last_visit(str(Path("r1"))) is None


def test_pull_interactive_without_a_tty_does_nothing(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(
        upstream, "walk_upstream", lambda *_a, **_k: pytest.fail("must not fetch without a TTY")
    )
    upstream.pull_interactive(Settings(folders=(Path("root"),)), pull_store)
    assert "interactive terminal" in capsys.readouterr().out


def test_nothing_behind_says_so(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_pull(monkeypatch, pull_store, []) == []
    assert "No repos behind" in capsys.readouterr().out


def test_up_to_date_repo_is_recorded_as_checked(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    """Nothing to pull means nothing to ask about, so the walk itself settles the repo."""
    _held_back(monkeypatch, pull_store, counts="0\t0\n")
    assert pull_store.last_visit(str(Path("repo0"))) is not None


def test_repo_without_a_tracking_branch_is_recorded_as_checked(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    """The question does not apply to it -- re-fetching it every run is pure cost."""
    _held_back(monkeypatch, pull_store, upstream_name=None)
    assert pull_store.last_visit(str(Path("repo0"))) is not None


def test_checked_repo_is_not_fetched_again_within_the_window(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    _held_back(monkeypatch, pull_store, counts="0\t0\n")
    assert _held_back(monkeypatch, pull_store, counts="0\t0\n") == []


def test_abort_still_settles_the_repos_that_needed_nothing(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    """Abort records nothing for the repo it was asked about, but an up-to-date one was
    already settled during the fetch, so the next run leaves it alone."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(scanner, "find_repos", lambda *_a, **_k: iter([Path("clean")]))
    _stub_git(monkeypatch, counts="0\t0\n")
    monkeypatch.setattr(menu, "choose", lambda _items, _title: "a")
    upstream.pull_interactive(Settings(folders=(Path("root"),)), pull_store)
    assert pull_store.last_visit(str(Path("clean"))) is not None
