"""Shared helpers for the committer tests: fake repo statuses and scripted menu input."""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo_status_check import menu
from git_repo_status_check.models import RepoStatus


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
