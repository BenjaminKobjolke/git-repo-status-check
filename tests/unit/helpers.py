"""Shared helpers for the committer tests: fake repo statuses and scripted menu input."""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo_status_check.models import RepoStatus


def _statuses(n: int) -> list[RepoStatus]:
    return [RepoStatus(path=Path(f"repo{i}"), dirty_count=1) for i in range(n)]


def _answers(monkeypatch: pytest.MonkeyPatch, *choices: str) -> None:
    """Feed the given menu choices to input() in order."""
    it = iter(choices)
    monkeypatch.setattr("builtins.input", lambda _: next(it))
