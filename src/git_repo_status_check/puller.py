"""``--pull-ask``: the menu for a repo found behind its upstream, and the mode's entry point.

The measurement and the walk-and-ask loop live in ``upstream`` (shared with ``--push-ask``);
this module, like ``pusher``, only defines what the pull side asks and runs.

User-facing I/O (menus via menu.py, print) like upstream.py, not logging.
"""

from __future__ import annotations

import os
import time

from . import menu
from .constants import (
    GIT_TERMINAL_PROMPT_ENV,
    GIT_TERMINAL_PROMPT_OFF,
    MENU_ABORTED,
    PULL_MENU,
    PULL_MENU_RENAME,
    PULL_MENU_STASH,
    PULL_NEEDS_TTY,
    PULL_NONE_BEHIND,
    SKIPPED_WORK_FETCHING,
)
from .mute_store import MuteStore
from .repo_actions import run_pull, run_rename, run_stash
from .settings import Settings
from .upstream import AskMode, RepoUpstream, ask_interactive, measure


def pull_menu(dirty_count: int, rename_prefix: str | None = None) -> tuple[tuple[str, str], ...]:
    """``PULL_MENU`` with the stash and rename entries spliced in after *Pull*, when they apply.

    Built per repo rather than being a constant: stashing is only useful — and only works —
    on a repo with local changes, and renaming needs a ``rename_prefix`` to rename to. An
    entry that cannot work is left out rather than shown and failing.
    """
    pull, *rest = PULL_MENU
    extra: list[tuple[str, str]] = []
    if dirty_count:
        extra.append(PULL_MENU_STASH)
    if rename_prefix:
        extra.append(PULL_MENU_RENAME)
    return (pull, *extra, *rest)


def prompt_repo(found: RepoUpstream, store: MuteStore, rename_prefix: str | None = None) -> bool:
    """Ask about one repo until it is settled; False when the user chose Abort.

    The menu comes back after a failed pull (or a failed stash, or a refused rename) instead
    of the walk moving on: the usual failure is local changes standing in the way, and the
    answer to it — stash, then pull — is an entry on the same menu.
    """
    dirty = found.dirty_count
    while True:
        choice = menu.choose(pull_menu(dirty, rename_prefix), found.header())
        if choice == "a":
            print(MENU_ABORTED)
            return False
        if choice == "s":
            return True
        if choice == "m":
            store.mute(str(found.path), time.time() + menu.ask_timeframe())
            return True
        # Renamed out of the way: there is no longer a repo at this path to pull into.
        if choice == "r":
            if run_rename(found.path, rename_prefix):
                return True
            menu.pause()
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


PULL_MODE: AskMode[RepoUpstream] = AskMode(
    measure=measure,
    prompt=lambda found, store, settings: prompt_repo(found, store, settings.rename_prefix),
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
