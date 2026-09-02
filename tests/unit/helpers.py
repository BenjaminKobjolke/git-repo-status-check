"""Shared unit-test helpers: fake repo statuses, scripted menu input, stubbed git.

``_behind`` / ``_run_pull`` drive the ``--pull-ask`` menu loop; both pull test modules use
them, which is why they are here rather than in either one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from git_repo_status_check import menu, upstream
from git_repo_status_check.models import RepoStatus
from git_repo_status_check.mute_store import MuteStore
from git_repo_status_check.settings import Settings


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


def _run_pull(
    monkeypatch: pytest.MonkeyPatch,
    store: MuteStore,
    repos: list[upstream.RepoUpstream],
    *choices: str,
    prompt_all: bool = False,
    fail_pulls: int = 0,
) -> list[Path]:
    """Drive ``pull_interactive`` over ``repos`` with scripted menu answers; return pulls."""
    pulled: list[Path] = []
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(upstream, "walk_upstream", lambda *_a, **_k: iter(repos))
    def _pull(path: Path) -> bool:
        pulled.append(path)
        return len(pulled) > fail_pulls


    monkeypatch.setattr(upstream, "run_pull", _pull)
    it = iter(choices)
    monkeypatch.setattr(menu, "choose", lambda _items, _title: next(it))
    monkeypatch.setattr(menu, "pause", lambda: None)
    upstream.pull_interactive(Settings(folders=(Path("root"),)), store, prompt_all=prompt_all)
    return pulled
