"""Unit tests for the --fix-line-endings repair — git calls are stubbed, no real repo."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from git_repo_status_check import line_endings
from git_repo_status_check.settings import Settings


def _stub_git(
    monkeypatch: pytest.MonkeyPatch,
    *,
    clean_at: str | None,
    original: str = "",
) -> list[tuple[str, ...]]:
    """Record every git call; the repo only agrees with its index once autocrlf is ``clean_at``.

    ``clean_at`` of None means no value ever helps (a .gitattributes rule wins). ``original``
    is what ``config --get`` answers before anything is written. ``git add`` is modelled as
    the stat refresh it is: the file drops out of the status listing once it is run.
    """
    calls: list[tuple[str, ...]] = []
    current = original
    refreshed = False

    def run_git(_repo: Path, args: tuple[str, ...]) -> str | None:
        nonlocal current, refreshed
        calls.append(args)
        if args[:2] == ("config", "--local"):
            return f"{current}\n"
        if args[0] == "config":
            current = "" if "--unset" in args else args[-1]
        if args[0] == "diff":
            return "" if current == clean_at else "noise.txt\0"
        if args[0] == "add":
            refreshed = True
        return ""

    monkeypatch.setattr(line_endings, "run_git", run_git)
    monkeypatch.setattr(
        line_endings,
        "changed_paths",
        lambda _repo: set() if refreshed and current == clean_at else {"noise.txt"},
    )
    return calls


def test_repair_settles_on_the_value_that_makes_the_repo_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # LF blobs with a CRLF worktree: turning the conversion on normalizes them back.
    _stub_git(monkeypatch, clean_at="true", original="false")
    result = line_endings.repair(Path("repo"), {"noise.txt"})
    assert result.autocrlf == "true"
    assert result.fixed == 1


def test_repair_falls_through_to_the_second_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_git(monkeypatch, clean_at="false")
    assert line_endings.repair(Path("repo"), {"noise.txt"}).autocrlf == "false"


def test_repair_never_stages_while_content_still_differs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `git add` refreshes stale index stat data, but it would stage a real change if the
    # conversion had not already made the file and its blob identical.
    calls = _stub_git(monkeypatch, clean_at=None)
    line_endings.repair(Path("repo"), {"noise.txt"})
    assert not [args for args in calls if args[0] == "add"]


def test_repair_rolls_back_when_no_value_helps(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_git(monkeypatch, clean_at=None, original="input")
    result = line_endings.repair(Path("repo"), {"noise.txt"})
    assert result.autocrlf is None
    assert result.fixed == 0
    assert calls[-1] == ("config", "core.autocrlf", "input")  # previous value restored


def test_repair_unsets_when_there_was_no_local_value(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_git(monkeypatch, clean_at=None)
    line_endings.repair(Path("repo"), {"noise.txt"})
    assert calls[-1] == ("config", "--unset", "core.autocrlf")


def test_fix_interactive_without_a_tty_does_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(
        line_endings, "find_repos", lambda *_a, **_k: pytest.fail("must not walk without a TTY")
    )
    line_endings.fix_interactive(Settings(folders=(Path("root"),)))
    assert "interactive terminal" in capsys.readouterr().out


def test_fix_interactive_abort_stops_before_the_second_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repaired: list[Path] = []
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(line_endings, "find_repos", lambda *_a, **_k: iter([tmp_path, tmp_path]))
    monkeypatch.setattr(line_endings, "line_ending_only_paths", lambda _repo: {"noise.txt"})
    monkeypatch.setattr(line_endings, "input", lambda _prompt: "a", raising=False)
    monkeypatch.setattr(line_endings, "repair", lambda repo, _noisy: repaired.append(repo))
    line_endings.fix_interactive(Settings(folders=(tmp_path,)))
    assert repaired == []
