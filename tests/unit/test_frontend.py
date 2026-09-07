"""Unit tests for the frontend port: delegation, the default, and the terminal implementation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import frontend, menu, reporter
from git_repo_status_check.menu import TerminalFrontend


class _Recording:
    """A frontend that records every call -- the shape any implementation must honour."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def choose(self, items: frontend.MenuItems, title: str) -> str:
        self.calls.append(("choose", (tuple(items), title)))
        return items[0][1]

    def ask_text(self, prompt: str) -> str:
        self.calls.append(("ask_text", (prompt,)))
        return "2h"

    def pause(self) -> None:
        self.calls.append(("pause", ()))

    def is_interactive(self) -> bool:
        return True

    def progress(self, path: object) -> None:
        self.calls.append(("progress", (path,)))

    def clear_progress(self) -> None:
        self.calls.append(("clear_progress", ()))

    def run_live(self, command: str | tuple[str, ...], cwd: Path, shell: bool = False) -> int:
        self.calls.append(("run_live", (command, cwd, shell)))
        return 0


@pytest.fixture(autouse=True)
def _reset_frontend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(frontend, "_current", None)


def test_default_frontend_is_the_terminal() -> None:
    assert isinstance(frontend.get(), TerminalFrontend)
    assert frontend.get() is frontend.get()  # built once, then reused


def test_menu_and_reporter_delegate_to_the_installed_frontend() -> None:
    recording = _Recording()
    frontend.install(recording)

    assert menu.choose((("Yes", "y"),), "title") == "y"
    assert menu.ask_text("prompt? ") == "2h"
    menu.pause()
    assert menu.is_interactive() is True
    reporter.progress(Path("repo"))
    reporter.clear_progress()

    assert [name for name, _ in recording.calls] == [
        "choose",
        "ask_text",
        "pause",
        "progress",
        "clear_progress",
    ]
    assert recording.calls[0][1] == ((("Yes", "y"),), "title")


def test_ask_timeframe_uses_the_installed_frontend_for_custom_input() -> None:
    class Custom(_Recording):
        def choose(self, items: frontend.MenuItems, title: str) -> str:
            return "custom"

    frontend.install(Custom())
    assert menu.ask_timeframe() == 2 * 3600.0


def test_terminal_is_interactive_follows_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert TerminalFrontend().is_interactive() is False
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    assert TerminalFrontend().is_interactive() is True


def test_terminal_run_live_inherits_the_console(monkeypatch: pytest.MonkeyPatch) -> None:
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = 3
    run = MagicMock(return_value=result)
    monkeypatch.setattr(subprocess, "run", run)

    code = TerminalFrontend().run_live("do-commit", Path("repo"), shell=True)

    assert code == 3
    run.assert_called_once_with("do-commit", shell=True, cwd=str(Path("repo")), check=False)


def test_terminal_choose_refuses_without_a_console(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(RuntimeError):
        TerminalFrontend().choose((("Yes", "y"),), "title")
