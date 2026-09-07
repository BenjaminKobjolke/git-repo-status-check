"""The console port: what a mode needs from its user interface, and which one is installed.

Every ask-mode talks to the user through the same few calls -- a menu, a typed answer, a
pause, a progress line, a child process whose output the user should see -- and gates on
whether anyone is there to answer at all. Those calls are gathered into one ``Frontend``
protocol so the same mode loops run unchanged under a terminal (``menu.TerminalFrontend``)
and under the Qt window (``gui.qt_frontend.QtFrontend``). Modes never pick the frontend:
they call ``get()``, and the entry point installs the right one.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

# A menu pairs each visible label with the action value the caller switches on.
MenuItems = Sequence[tuple[str, str]]


class RunCancelled(Exception):
    """The user stopped a run from the GUI -- the Ctrl-C of a frontend without a console."""


class Frontend(Protocol):
    """Everything a mode asks of the user interface."""

    def choose(self, items: MenuItems, title: str) -> str:
        """Show a menu of ``items`` and return the chosen entry's action value."""
        ...

    def ask_text(self, prompt: str) -> str:
        """Read a free-text answer -- a menu cannot express an arbitrary duration."""
        ...

    def pause(self) -> None:
        """Hold printed output on screen until the user has read it."""
        ...

    def is_interactive(self) -> bool:
        """Whether anyone can answer a menu at all (a TTY, or a window)."""
        ...

    def progress(self, path: object) -> None:
        """Narrate the walk: the repo currently being scanned."""
        ...

    def clear_progress(self) -> None:
        """Remove the progress narration before the report is printed."""
        ...

    def run_live(self, command: str | tuple[str, ...], cwd: Path, shell: bool = False) -> int:
        """Run a child in ``cwd`` with its output shown to the user; return its exit code."""
        ...


_current: Frontend | None = None


def get() -> Frontend:
    """The installed frontend; the terminal one until something else is installed.

    The default is imported lazily so the GUI never loads ``pick``/``blessed`` -- they are
    only needed once a console menu is actually drawn.
    """
    global _current
    if _current is None:
        from .menu import TerminalFrontend

        _current = TerminalFrontend()
    return _current


def install(frontend: Frontend) -> None:
    """Make ``frontend`` the one every mode talks to (the entry point calls this once)."""
    global _current
    _current = frontend
