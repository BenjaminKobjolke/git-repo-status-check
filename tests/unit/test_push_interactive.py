"""Unit tests for the --push-ask menu loop: what each answer does, and what it records.

The measurement that feeds it is tested in ``test_pusher``; git calls are stubbed throughout.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from git_repo_status_check import menu, pusher, upstream
from git_repo_status_check.constants import PUSH_MENU
from git_repo_status_check.mute_store import MuteStore
from git_repo_status_check.settings import Settings

from .helpers import _ahead, _one_repo_console, _run_push


def test_push_runs_git_push_for_the_repo(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore
) -> None:
    assert _run_push(monkeypatch, push_store, [_ahead("repo0")], "p") == [
        (Path("repo0"), ("push",))
    ]


def test_push_u_uses_the_repos_own_args(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore
) -> None:
    repo = _ahead("repo0", upstream=None)
    assert _run_push(monkeypatch, push_store, [repo], "p") == [
        (Path("repo0"), ("push", "-u", "origin", "main"))
    ]


def test_skip_does_not_push(monkeypatch: pytest.MonkeyPatch, push_store: MuteStore) -> None:
    assert _run_push(monkeypatch, push_store, [_ahead("repo0")], "s") == []


def test_abort_stops_before_the_second_repo(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore
) -> None:
    assert (
        _run_push(
            monkeypatch,
            push_store,
            [_ahead("r0"), _ahead("r1")],
            "a",
            "p",
            expect_completed=False,
        )
        == []
    )


def test_mute_writes_to_the_push_store_only(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore, pull_store: MuteStore
) -> None:
    monkeypatch.setattr(menu, "ask_timeframe", lambda: 3600.0)
    _run_push(monkeypatch, push_store, [_ahead("repo0")], "m")
    assert push_store.muted_until(str(Path("repo0")), 0.0) is not None
    assert pull_store.muted_until(str(Path("repo0")), 0.0) is None


def test_failed_push_re_asks_then_skip_moves_on(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore
) -> None:
    pushed = _run_push(
        monkeypatch, push_store, [_ahead("r0"), _ahead("r1")], "p", "s", "s", fail_pushes=1
    )
    assert pushed == [(Path("r0"), ("push",))]


def test_pull_entry_pulls_then_re_asks(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore
) -> None:
    pulled: list[Path] = []

    def _pull(path: Path) -> bool:
        pulled.append(path)
        return True

    monkeypatch.setattr(pusher, "run_pull", _pull)
    pushed = _run_push(monkeypatch, push_store, [_ahead("repo0")], "l", "p")
    assert pulled == [Path("repo0")]
    assert pushed == [(Path("repo0"), ("push",))]


def test_menu_with_upstream_is_the_plain_one() -> None:
    assert pusher.push_menu(_ahead("repo0")) == PUSH_MENU


def test_menu_without_upstream_names_the_push_u_and_drops_pull() -> None:
    """Nothing to pull from without a tracking branch, so the entry would only fail."""
    labels = [label for label, _ in pusher.push_menu(_ahead("repo0", upstream=None))]
    assert labels == ["Push -u origin main", "Skip", "Mute repo", "Abort"]


def _held_back(
    monkeypatch: pytest.MonkeyPatch,
    store: MuteStore,
    *,
    prompt_all: bool = False,
    counts: str = "0\t1\n",
) -> list[tuple[str, ...]]:
    """Run the whole mode over one repo with git recorded; return the git calls it made."""
    calls: list[tuple[str, ...]] = []

    def run_git(_repo: Path, args: tuple[str, ...], quiet: bool = False) -> str | None:
        calls.append(args)
        return "origin/main\n" if args[0] == "rev-parse" else counts

    monkeypatch.setattr(upstream, "run_git", run_git)
    monkeypatch.setattr(pusher, "run_git", run_git)
    monkeypatch.setattr(pusher, "dirty_info", lambda _repo: (0, 0.0))
    _one_repo_console(monkeypatch)
    pusher.push_interactive(Settings(folders=(Path("root"),)), store, prompt_all=prompt_all)
    return calls


def test_muted_repo_costs_no_git_call(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore, capsys: pytest.CaptureFixture[str]
) -> None:
    push_store.mute(str(Path("repo0")), 2_000_000_000.0)
    assert _held_back(monkeypatch, push_store) == []
    assert "Skipped 1 repo(s) without checking" in capsys.readouterr().out


def test_recently_visited_repo_costs_no_git_call(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore
) -> None:
    push_store.record_visit(str(Path("repo0")), time.time())
    assert _held_back(monkeypatch, push_store) == []


def test_prompt_all_checks_held_back_repos(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore
) -> None:
    push_store.mute(str(Path("repo0")), 2_000_000_000.0)
    assert _held_back(monkeypatch, push_store, prompt_all=True) != []


def test_repo_with_nothing_to_push_is_recorded_as_checked(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore
) -> None:
    _held_back(monkeypatch, push_store, counts="0\t0\n")
    assert push_store.last_visit(str(Path("repo0"))) is not None


def test_abort_still_records_the_repo_you_were_shown(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore
) -> None:
    _run_push(monkeypatch, push_store, [_ahead("r0"), _ahead("r1")], "a", expect_completed=False)
    assert push_store.last_visit(str(Path("r0"))) is not None
    assert push_store.last_visit(str(Path("r1"))) is None


def test_nothing_ahead_says_so(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_push(monkeypatch, push_store, []) == []
    assert "No repos with unpushed commits" in capsys.readouterr().out


def test_push_interactive_without_a_tty_does_nothing(
    monkeypatch: pytest.MonkeyPatch, push_store: MuteStore, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(
        upstream, "walk_found", lambda *_a, **_k: pytest.fail("must not walk without a TTY")
    )
    pusher.push_interactive(Settings(folders=(Path("root"),)), push_store)
    assert "interactive terminal" in capsys.readouterr().out
