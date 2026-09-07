"""Terminal menu helpers -- the single wrapper around ``pick``, and the console frontend.

Every interactive prompt in the app goes through here, so the backend, the indicator
style, the Ctrl-C behaviour and the "hold printed output on screen" pause are defined once
(see CODING_RULES.md, "CLI Menus"). No other module imports ``pick``.

Callers import the module (``from . import menu``) rather than the functions, so tests can
replace ``menu.choose`` / ``menu.ask_text`` in one place. The module functions delegate to
whichever ``frontend`` is installed; ``TerminalFrontend`` below is the console one, and the
GUI installs its own (see ``frontend.py``).

The backend is ``blessed``, not the ``pick`` default of curses. On Windows, any child
process that inherits the console (``git pull``, the commit command) permanently stops
curses translating arrow keys into ``KEY_UP`` / ``KEY_DOWN`` for the rest of the process:
the keys still arrive, but as raw ``ESC [ A`` sequences that ``pick`` ignores, so the next
menu draws and then accepts nothing. Measured, not guessed -- capturing the child's output
avoids it, but that would cost the live output of pull and commit. ``blessed`` decodes
those sequences itself, so the menus keep working and subprocesses keep the console.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from pick import pick

from . import frontend
from .constants import (
    MENU_BACKEND,
    MENU_INDICATOR,
    MENU_NEEDS_TTY,
    MENU_PAUSE_PROMPT,
    MUTE_CHOICE_CUSTOM,
    MUTE_CUSTOM_PROMPT,
    MUTE_MENU,
    MUTE_MENU_TITLE,
    MUTE_PROMPT_HELP,
    PROGRESS_LINE,
)
from .duration import parse_duration
from .frontend import MenuItems

__all__ = ["MenuItems", "TerminalFrontend", "ask_text", "ask_timeframe", "choose", "pause"]


class TerminalFrontend:
    """The console: ``pick`` menus, ``input``, a ``\\r`` progress line, children on the TTY."""

    def choose(self, items: MenuItems, title: str) -> str:
        """Show an arrow-key menu of ``items`` and return the chosen entry's action value.

        ``pick`` returns an index, never free text, so there is no invalid-answer branch
        to re-prompt. Ctrl-C leaves the program rather than bubbling a half-drawn screen
        upwards.
        """
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            # Without a console the menu would block on a key that can never arrive.
            raise RuntimeError(MENU_NEEDS_TTY)
        try:
            _, index = pick(
                [label for label, _ in items],
                title,
                indicator=MENU_INDICATOR,
                backend=MENU_BACKEND,
            )
        except KeyboardInterrupt:
            sys.exit(1)
        # pick is untyped, so its index arrives as Any; narrow it before indexing.
        return items[int(index)][1]

    def ask_text(self, prompt: str) -> str:
        return input(prompt)

    def pause(self) -> None:
        """Wait for Enter: the next menu takes the whole screen, hiding what was printed."""
        input(MENU_PAUSE_PROMPT)

    def is_interactive(self) -> bool:
        """stdin only: the modes' own historical gate, and what the tests stub."""
        return sys.stdin.isatty()

    def progress(self, path: object) -> None:
        """Overwrite one stderr line with the repo currently being scanned (TTY only)."""
        if not sys.stderr.isatty():
            return
        width = shutil.get_terminal_size().columns
        line = PROGRESS_LINE.format(path=path)[: width - 1]
        print(f"\r{line:<{width - 1}}", end="", file=sys.stderr, flush=True)

    def clear_progress(self) -> None:
        """Blank the progress line so it doesn't linger before the report (TTY only)."""
        if not sys.stderr.isatty():
            return
        width = shutil.get_terminal_size().columns
        print(f"\r{'':<{width - 1}}\r", end="", file=sys.stderr, flush=True)

    def run_live(self, command: str | tuple[str, ...], cwd: Path, shell: bool = False) -> int:
        """Run ``command`` inheriting the console, so the user sees progress and any
        credential prompt. Not captured like ``scanner.run_git``."""
        return subprocess.run(command, shell=shell, cwd=str(cwd), check=False).returncode


def choose(items: MenuItems, title: str) -> str:
    """Show a menu of ``items`` and return the chosen entry's action value.

    ``items`` pairs each visible label with the action string the caller switches on, so an
    option can never be displayed without a handler behind it.
    """
    return frontend.get().choose(items, title)


def ask_text(prompt: str) -> str:
    """Read a free-text answer -- a menu cannot express an arbitrary duration."""
    return frontend.get().ask_text(prompt)


def pause() -> None:
    """Hold printed output on screen until the user has read it."""
    frontend.get().pause()


def is_interactive() -> bool:
    """Whether a menu can be answered at all; the modes' no-op gate."""
    return frontend.get().is_interactive()


def ask_timeframe() -> float:
    """Pick a mute timeframe (1d/1w/1m or custom), re-asking until valid. Returns seconds.

    Only the custom entry falls back to typed input -- a menu cannot express an arbitrary
    duration. Lives here rather than with either ask-mode because both mute repos, and a
    second copy of the prompt would be the only way for the two to disagree.
    """
    while True:
        choice = choose(MUTE_MENU, MUTE_MENU_TITLE)
        text = ask_text(MUTE_CUSTOM_PROMPT) if choice == MUTE_CHOICE_CUSTOM else choice
        seconds = parse_duration(text)
        if seconds is not None:
            return seconds
        print(MUTE_PROMPT_HELP)
        pause()
