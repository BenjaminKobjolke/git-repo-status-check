"""``--pull-ask``: the menu for a repo found behind its upstream, and the mode's entry point.

The measurement and the walk-and-ask loop live in ``upstream`` (shared with ``--push-ask``);
this module, like ``pusher``, only defines what the pull side asks and runs.

User-facing I/O (menus via menu.py, print) like upstream.py, not logging.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from . import menu
from .constants import (
    GIT_TERMINAL_PROMPT_ENV,
    GIT_TERMINAL_PROMPT_OFF,
    MENU_ABORTED,
    MORE_MENU_TITLE,
    PULL_MENU,
    PULL_MENU_STASH,
    PULL_MORE_MENU,
    PULL_NEEDS_TTY,
    PULL_NONE_BEHIND,
    SKIPPED_WORK_FETCHING,
)
from .mute_store import MuteStore
from .repo_actions import run_explorer, run_pull, run_rename, run_stash
from .settings import Settings
from .upstream import AskMode, RepoUpstream, ask_interactive, measure


def pull_menu(dirty_count: int) -> tuple[tuple[str, str], ...]:
    """``PULL_MENU`` with the stash-and-pull entry spliced in after *Pull*, when it applies.

    Built per repo rather than being a constant: stashing is only useful — and only works —
    on a repo with local changes. On a clean one the entry is left out rather than shown
    and failing.
    """
    if not dirty_count:
        return PULL_MENU
    pull, *rest = PULL_MENU
    return (pull, PULL_MENU_STASH, *rest)


def prompt_repo(found: RepoUpstream, store: MuteStore, settings: Settings) -> bool:
    """Ask about one repo until it is settled; False when the user chose Abort.

    The menu comes back after a failed pull (or a failed stash) instead of the walk moving
    on: the usual failure is local changes standing in the way, and the answer to it —
    stash, then pull — is an entry on the same menu.
    """
    dirty = found.dirty_count
    while True:
        choice = menu.choose(pull_menu(dirty), found.header())
        if choice == "a":
            print(MENU_ABORTED)
            return False
        if choice == "s":
            return True
        if choice == "m":
            store.mute(str(found.path), time.time() + menu.ask_timeframe())
            return True
        if choice == "more":
            sub = _more_menu(found.path, settings)
            # Renamed out of the way: there is no longer a repo at this path to pull into.
            if sub == "renamed":
                return True
            if sub == "stashed":
                dirty = 0
            continue
        if choice == "t":
            if not run_stash(found.path):
                menu.pause()
                continue
            # Stashed: the tree is clean, so the stash entry drops off the retry menu.
            dirty = 0
        pulled = run_pull(found.path)
        # The next menu repaints the whole screen, so hold the pull output until read.
        menu.pause()
        if pulled:
            return True


def _more_menu(path: Path, settings: Settings) -> str:
    """Submenu: explorer / rename / stash / back. Returns 'renamed', 'stashed' or 'back'.

    The explorer entry prints and re-prompts; so do a refused rename and a failed stash.
    A stash that worked goes back to the top menu: pulling stays a separate decision, and
    the clean tree drops *Stash changes and pull* from it.
    """
    while True:
        choice = menu.choose(PULL_MORE_MENU, MORE_MENU_TITLE.format(path=path))
        if choice == "e":
            run_explorer(path, settings.file_explorer)
        elif choice == "r":
            if run_rename(path, settings.rename_prefix):
                return "renamed"
        elif choice == "s":
            if run_stash(path):
                menu.pause()
                return "stashed"
        else:
            return "back"
        # The next menu repaints the whole screen, so hold the output until read.
        menu.pause()


PULL_MODE: AskMode[RepoUpstream] = AskMode(
    measure=measure,
    prompt=prompt_repo,
    needs_tty=PULL_NEEDS_TTY,
    none_found=PULL_NONE_BEHIND,
    work=SKIPPED_WORK_FETCHING,
)


def pull_interactive(settings: Settings, store: MuteStore, prompt_all: bool = False) -> bool:
    """``ask_interactive`` in pull mode, with git's credential prompt switched off meanwhile.

    A remote wanting credentials would block the fetch on a console prompt and hang the
    whole walk. Set for the process rather than threaded through every run_git call, and
    restored afterwards: the push stage of ``--sync-ask`` runs in the same process and may
    legitimately have to ask for credentials. False when the user chose Abort.
    """
    previous = os.environ.get(GIT_TERMINAL_PROMPT_ENV)
    os.environ[GIT_TERMINAL_PROMPT_ENV] = GIT_TERMINAL_PROMPT_OFF
    try:
        return ask_interactive(settings, store, PULL_MODE, prompt_all)
    finally:
        if previous is None:
            os.environ.pop(GIT_TERMINAL_PROMPT_ENV, None)
        else:
            os.environ[GIT_TERMINAL_PROMPT_ENV] = previous
