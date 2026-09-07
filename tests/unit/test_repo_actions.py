"""Unit tests for the shared repo actions — git is stubbed, nothing touches a real repo."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import repo_actions
from git_repo_status_check.constants import GIT_CHECKOUT_HEAD_STDIN_PATHS, NUL


def _stub_pull(
    monkeypatch: pytest.MonkeyPatch, noisy: set[str]
) -> tuple[list[tuple[str, ...]], list[tuple[str, ...]]]:
    """Record captured git calls (with their stdin) and streamed git calls, in order.

    The pull itself streams through the terminal frontend's ``subprocess.run``; the reset
    goes through ``run_git``.
    Both are recorded into ``order`` so a test can assert the reset comes first.
    """
    captured: list[tuple[str, ...]] = []
    order: list[tuple[str, ...]] = []

    def run_git(_repo: Path, args: tuple[str, ...], input: str | None = None) -> str | None:
        captured.append((*args, input or ""))
        order.append(args)
        return ""

    def run(argv: tuple[str, ...], **_kwargs: object) -> MagicMock:
        order.append(argv[3:])
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = 0
        return result

    monkeypatch.setattr(repo_actions, "line_ending_only_paths", lambda _repo: noisy)
    monkeypatch.setattr(repo_actions, "run_git", run_git)
    monkeypatch.setattr(subprocess, "run", run)
    return captured, order


def test_pull_resets_line_ending_noise_from_head_before_pulling(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Two files whose only difference is a CR at end of line: git would refuse the merge
    # over them although nothing was edited, so they are restored from HEAD first.
    captured, order = _stub_pull(monkeypatch, {"b.txt", "a.txt"})
    assert repo_actions.run_pull(Path("repo")) is True
    assert captured == [(*GIT_CHECKOUT_HEAD_STDIN_PATHS, f"a.txt{NUL}b.txt")]
    assert order[0] == GIT_CHECKOUT_HEAD_STDIN_PATHS
    assert order[1][0] == "pull"
    assert "Reset 2 line-ending-only file(s)" in capsys.readouterr().out


def test_pull_on_a_repo_without_noise_touches_nothing_first(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured, order = _stub_pull(monkeypatch, set())
    assert repo_actions.run_pull(Path("repo")) is True
    assert captured == []
    assert [args[0] for args in order] == ["pull"]
    assert "Reset" not in capsys.readouterr().out
