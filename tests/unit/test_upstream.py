"""Unit tests for the --pull-ask mode -- git calls are stubbed, no real repo, no network."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from git_repo_status_check import menu, upstream
from git_repo_status_check.mute_store import MuteStore
from git_repo_status_check.settings import Settings


def _stub_git(
    monkeypatch: pytest.MonkeyPatch,
    *,
    upstream_name: str | None = "origin/main",
    counts: str | None = "2\t3\n",
) -> list[tuple[str, ...]]:
    """Record every git call; answer the three commands ``scan_upstream`` issues.

    ``None`` for either answer models the real failure modes: no tracking branch
    (``rev-parse @{u}`` exits non-zero) and an unreadable rev-list.
    """
    calls: list[tuple[str, ...]] = []

    def run_git(_repo: Path, args: tuple[str, ...], quiet: bool = False) -> str | None:
        calls.append(args)
        if args[0] == "rev-parse":
            return None if upstream_name is None else f"{upstream_name}\n"
        if args[0] == "rev-list":
            return counts
        return ""

    monkeypatch.setattr(upstream, "run_git", run_git)
    monkeypatch.setattr(upstream, "dirty_info", lambda _repo: (0, 0.0))
    return calls


def _scan(monkeypatch: pytest.MonkeyPatch, repos: list[Path]) -> list[upstream.RepoUpstream]:
    monkeypatch.setattr(upstream, "walk_repos", lambda *_a, **_k: iter(repos))
    return upstream.scan_upstream(Settings(folders=(Path("root"),)))


def test_behind_and_ahead_counts_are_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, counts="2\t3\n")
    results = _scan(monkeypatch, [Path("repo0")])
    assert len(results) == 1
    assert results[0].behind == 2
    assert results[0].upstream == "origin/main"


def test_repo_level_with_upstream_is_not_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, counts="0\t0\n")
    assert _scan(monkeypatch, [Path("repo0")]) == []


def test_repo_without_tracking_branch_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_git(monkeypatch, upstream_name=None)
    assert _scan(monkeypatch, [Path("repo0")]) == []
    # Bailing out early also means the expensive rev-list is never run.
    assert not [args for args in calls if args[0] == "rev-list"]


def test_unreadable_rev_list_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, counts=None)
    assert _scan(monkeypatch, [Path("repo0")]) == []


def test_unparsable_rev_list_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    # An answer that is not "<int>\t<int>" must not crash the whole walk.
    _stub_git(monkeypatch, counts="nonsense\n")
    assert _scan(monkeypatch, [Path("repo0")]) == []


def test_results_are_sorted_most_stale_first(monkeypatch: pytest.MonkeyPatch) -> None:
    behind = iter(["1\t0\n", "7\t0\n", "3\t0\n"])
    monkeypatch.setattr(upstream, "dirty_info", lambda _repo: (0, 0.0))
    monkeypatch.setattr(
        upstream,
        "run_git",
        lambda _repo, args, quiet=False: (
            "origin/main\n"
            if args[0] == "rev-parse"
            else next(behind)
            if args[0] == "rev-list"
            else ""
        ),
    )
    results = _scan(monkeypatch, [Path("a"), Path("b"), Path("c")])
    assert [r.behind for r in results] == [7, 3, 1]


def test_header_notes_uncommitted_files(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch)
    monkeypatch.setattr(upstream, "dirty_info", lambda _repo: (4, 0.0))
    header = _scan(monkeypatch, [Path("repo0")])[0].header()
    assert "2 commit" in header
    assert "origin/main" in header
    assert "4 uncommitted" in header


def test_header_omits_the_dirty_note_when_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch)
    assert "uncommitted" not in _scan(monkeypatch, [Path("repo0")])[0].header()


def _behind(path: str) -> upstream.RepoUpstream:
    return upstream.RepoUpstream(path=Path(path), upstream="origin/main", behind=1, dirty_count=0)


def _run(
    monkeypatch: pytest.MonkeyPatch,
    store: MuteStore,
    repos: list[upstream.RepoUpstream],
    *choices: str,
    prompt_all: bool = False,
) -> list[Path]:
    """Drive ``pull_interactive`` over ``repos`` with scripted menu answers; return pulls."""
    pulled: list[Path] = []
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(upstream, "scan_upstream", lambda *_a, **_k: repos)
    monkeypatch.setattr(upstream, "run_pull", lambda path: pulled.append(path))
    it = iter(choices)
    monkeypatch.setattr(menu, "choose", lambda _items, _title: next(it))
    monkeypatch.setattr(menu, "pause", lambda: None)
    upstream.pull_interactive(Settings(folders=(Path("root"),)), store, prompt_all=prompt_all)
    return pulled


def test_pull_runs_git_pull_for_the_repo(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    assert _run(monkeypatch, pull_store, [_behind("repo0")], "p") == [Path("repo0")]


def test_skip_does_not_pull(monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore) -> None:
    assert _run(monkeypatch, pull_store, [_behind("repo0")], "s") == []


def test_abort_stops_before_the_second_repo(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    # 'p' would fire on repo1 if abort did not stop the loop first.
    assert _run(monkeypatch, pull_store, [_behind("r0"), _behind("r1")], "a", "p") == []


def test_mute_writes_to_the_pull_store(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    monkeypatch.setattr(menu, "ask_timeframe", lambda: 3600.0)
    _run(monkeypatch, pull_store, [_behind("repo0")], "m")
    assert pull_store.muted_until(str(Path("repo0")), 0.0) is not None


def _held_back(
    monkeypatch: pytest.MonkeyPatch,
    store: MuteStore,
    *,
    prompt_all: bool = False,
    min_visit_age: float | None = 3600.0,
) -> list[tuple[str, ...]]:
    """Run the whole mode over one repo with git recorded; return the git calls it made.

    An empty list is the assertion that matters throughout: a held-back repo must cost no
    fetch at all, which is the point of filtering before the network rather than after.
    """
    calls = _stub_git(monkeypatch, counts="1\t0\n")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(upstream, "walk_repos", lambda *_a, **_k: iter([Path("repo0")]))
    monkeypatch.setattr(upstream, "run_pull", lambda _path: None)
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
    _run(monkeypatch, pull_store, [_behind("repo0")], "s")
    assert pull_store.last_visit(str(Path("repo0"))) is not None


def test_abort_records_no_visit(monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore) -> None:
    # You did not decide about that repo, so the next run must still fetch and offer it.
    _run(monkeypatch, pull_store, [_behind("repo0")], "a")
    assert pull_store.last_visit(str(Path("repo0"))) is None


def test_pull_interactive_without_a_tty_does_nothing(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(
        upstream, "scan_upstream", lambda *_a, **_k: pytest.fail("must not fetch without a TTY")
    )
    upstream.pull_interactive(Settings(folders=(Path("root"),)), pull_store)
    assert "interactive terminal" in capsys.readouterr().out


def test_nothing_behind_says_so(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(monkeypatch, pull_store, []) == []
    assert "No repos behind" in capsys.readouterr().out
