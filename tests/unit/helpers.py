"""Shared unit-test helpers: fake repo statuses, scripted menu input, stubbed git.

``_behind`` / ``_run_pull`` drive the ``--pull-ask`` menu loop; both pull test modules use
them, which is why they are here rather than in either one.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from git_repo_status_check import menu, puller, pusher, scanner, upstream
from git_repo_status_check.models import RepoStatus
from git_repo_status_check.mute_store import MuteStore
from git_repo_status_check.settings import Settings


def _one_repo_console(monkeypatch: pytest.MonkeyPatch, repo: str = "repo0") -> None:
    """A TTY, a walk of exactly one repo, and a menu that always answers Skip.

    The hold-back tests of both upstream modes start from this; only the git stub and the
    mode's entry point differ. ``find_repos`` is the stub point rather than the walk itself,
    so the skip filter and the progress line stay in the test.
    """
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(scanner, "find_repos", lambda *_a, **_k: iter([Path(repo)]))
    monkeypatch.setattr(menu, "choose", lambda _items, _title: "s")
    monkeypatch.setattr(menu, "pause", lambda: None)


def _statuses(n: int) -> list[RepoStatus]:
    return [RepoStatus(path=Path(f"repo{i}"), dirty_count=1) for i in range(n)]


def _answers(monkeypatch: pytest.MonkeyPatch, *choices: str) -> None:
    """Feed the given action values to the menu helper in order.

    Patches the helper rather than ``pick`` itself: ``pick`` needs a real terminal, and the
    modules under test call ``menu.choose`` so one patch covers every prompt. Free-text
    answers (custom mute durations) come off the same queue, and the Enter-to-continue
    pause is a no-op.
    """
    it = iter(choices)
    monkeypatch.setattr(menu, "choose", lambda items, title: next(it))
    monkeypatch.setattr(menu, "ask_text", lambda prompt: next(it))
    monkeypatch.setattr(menu, "pause", lambda: None)


def _stub_upstream_git(
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


def _behind(path: str, dirty_count: int = 0) -> upstream.RepoUpstream:
    return upstream.RepoUpstream(
        path=Path(path), upstream="origin/main", behind=1, dirty_count=dirty_count
    )


def _scripted_walk(
    monkeypatch: pytest.MonkeyPatch, repos: Sequence[object], choices: tuple[str, ...]
) -> None:
    """A TTY, a walk that yields exactly ``repos``, and a menu answering ``choices`` in order.

    The setup both upstream-mode drivers (``_run_pull`` / ``_run_push``) share.
    """
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(upstream, "walk_found", lambda *_a, **_k: iter(repos))
    it = iter(choices)
    monkeypatch.setattr(menu, "choose", lambda _items, _title: next(it))
    monkeypatch.setattr(menu, "pause", lambda: None)


def _run_pull(
    monkeypatch: pytest.MonkeyPatch,
    store: MuteStore,
    repos: list[upstream.RepoUpstream],
    *choices: str,
    prompt_all: bool = False,
    fail_pulls: int = 0,
    expect_completed: bool = True,
) -> list[Path]:
    """Drive ``pull_interactive`` over ``repos`` with scripted menu answers; return pulls.

    ``expect_completed`` is asserted against the mode's result: True unless Abort ended it.
    """
    pulled: list[Path] = []

    def _pull(path: Path) -> bool:
        pulled.append(path)
        return len(pulled) > fail_pulls

    monkeypatch.setattr(puller, "run_pull", _pull)
    _scripted_walk(monkeypatch, repos, choices)
    completed = puller.pull_interactive(
        Settings(folders=(Path("root"),)), store, prompt_all=prompt_all
    )
    assert completed is expect_completed
    return pulled


def _ahead(
    path: str, upstream: str | None = "origin/main", dirty_count: int = 0
) -> pusher.RepoAhead:
    return pusher.RepoAhead(
        path=Path(path),
        ahead=1,
        dirty_count=dirty_count,
        upstream=upstream,
        branch="main",
        remote="" if upstream else "origin",
    )


def _run_push(
    monkeypatch: pytest.MonkeyPatch,
    store: MuteStore,
    repos: list[pusher.RepoAhead],
    *choices: str,
    fail_pushes: int = 0,
    expect_completed: bool = True,
) -> list[tuple[Path, tuple[str, ...]]]:
    """Drive ``push_interactive`` over ``repos`` with scripted answers; return the pushes.

    ``expect_completed`` is asserted against the mode's result: True unless Abort ended it.
    """
    pushed: list[tuple[Path, tuple[str, ...]]] = []

    def _push(path: Path, push_args: tuple[str, ...]) -> bool:
        pushed.append((path, push_args))
        return len(pushed) > fail_pushes

    monkeypatch.setattr(pusher, "run_push", _push)
    _scripted_walk(monkeypatch, repos, choices)
    assert pusher.push_interactive(Settings(folders=(Path("root"),)), store) is expect_completed
    return pushed
