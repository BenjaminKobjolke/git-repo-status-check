"""Terminal menu helpers -- the single wrapper around ``pick``.

Every interactive prompt in the app goes through here, so the backend, the indicator
style, the Ctrl-C behaviour and the "hold printed output on screen" pause are defined once
(see CODING_RULES.md, "CLI Menus"). No other module imports ``pick``.

Callers import the module (``from . import menu``) rather than the functions, so tests can
replace ``menu.choose`` / ``menu.ask_text`` in one place.

The backend is ``blessed``, not the ``pick`` default of curses. On Windows, any child
process that inherits the console (``git pull``, the commit command) permanently stops
curses translating arrow keys into ``KEY_UP`` / ``KEY_DOWN`` for the rest of the process:
the keys still arrive, but as raw ``ESC [ A`` sequences that ``pick`` ignores, so the next
menu draws and then accepts nothing. Measured, not guessed -- capturing the child's output
avoids it, but that would cost the live output of pull and commit. ``blessed`` decodes
those sequences itself, so the menus keep working and subprocesses keep the console.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from pick import pick

from .constants import MENU_BACKEND, MENU_INDICATOR, MENU_NEEDS_TTY, MENU_PAUSE_PROMPT

MenuItems = Sequence[tuple[str, str]]


def choose(items: MenuItems, title: str) -> str:
    """Show an arrow-key menu of ``items`` and return the chosen entry's action value.

    ``items`` pairs each visible label with the action string the caller switches on, so an
    option can never be displayed without a handler behind it. ``pick`` returns an index,
    never free text, so there is no invalid-answer branch to re-prompt.
    Ctrl-C leaves the program rather than bubbling a half-drawn screen upwards.
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


def ask_text(prompt: str) -> str:
    """Read a free-text answer -- a menu cannot express an arbitrary duration."""
    return input(prompt)


def pause() -> None:
    """Wait for Enter: the next menu takes the whole screen, hiding what was just printed."""
    input(MENU_PAUSE_PROMPT)
