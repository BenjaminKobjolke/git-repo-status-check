"""``--pull-ask``: fetch every repo under the configured roots and offer to pull stale ones.

The normal report only ever asks the working tree, so a repo that is clean but sitting
behind its remote is invisible to it. This is the other direction — it asks the remote.
Self-contained like ``line_endings.py`` (its own walk, its own report, its own menu)
because it selects repos on a criterion the shared scan never computes.

User-facing I/O (menus via menu.py, print) like committer.py, not logging.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from . import menu
from .constants import (
    GIT_BEHIND_AHEAD,
    GIT_BEHIND_AHEAD_SEPARATOR,
    GIT_FETCH,
    GIT_TERMINAL_PROMPT_ENV,
    GIT_TERMINAL_PROMPT_OFF,
    GIT_UPSTREAM_NAME,
    MENU_ABORTED,
    PULL_HEADER,
    PULL_HEADER_DIRTY,
    PULL_MENU,
    PULL_MENU_RENAME,
    PULL_MENU_STASH,
    PULL_NEEDS_TTY,
    PULL_NONE_BEHIND,
    SKIPPED_WORK_FETCHING,
)
from .mute_store import MuteStore, ScanSkip
from .repo_actions import run_pull, run_rename, run_stash
from .reporter import clear_progress, progress, report_skipped
from .scanner import dirty_info, run_git, walk_repos
from .settings import Settings


@dataclass(frozen=True)
class RepoUpstream:
    """One repo that is behind its tracking branch, and how far."""

    path: Path
    upstream: str  # the tracking branch's name, e.g. "origin/main"
    behind: int
    dirty_count: int  # uncommitted files — shown as a warning, never a filter

    def header(self) -> str:
        """The one line that names this repo, reused as the menu title."""
        line = PULL_HEADER.format(path=self.path, behind=self.behind, upstream=self.upstream)
        if self.dirty_count:
            line += PULL_HEADER_DIRTY.format(count=self.dirty_count)
        return line


def measure(repo: Path) -> RepoUpstream | None:
    """Fetch ``repo``, then report how far behind its upstream it is — None when it is not.

    None also covers every repo the question simply does not apply to: no tracking branch,
    a detached HEAD, an unreachable remote. Those are ordinary across a folder full of
    repos rather than problems, which is why the git calls are made quietly.
    """
    run_git(repo, GIT_FETCH, quiet=True)
    name = (run_git(repo, GIT_UPSTREAM_NAME, quiet=True) or "").strip()
    if not name:
        return None
    behind = _behind_count(run_git(repo, GIT_BEHIND_AHEAD, quiet=True))
    if behind <= 0:
        return None
    return RepoUpstream(
        path=repo,
        upstream=name,
        behind=behind,
        dirty_count=dirty_info(repo)[0],
    )


def _behind_count(out: str | None) -> int:
    """Behind count from ``rev-list --left-right --count``'s ``<behind><TAB><ahead>``.

    0 whenever the answer is missing or is not the documented pair of integers: one
    malformed line must drop its own repo, never abort the walk over all the others.
    Ahead is read and discarded — nothing in this mode decides on it.
    """
    if out is None:
        return 0
    behind, _, _ahead = out.strip().partition(GIT_BEHIND_AHEAD_SEPARATOR)
    try:
        return int(behind)
    except ValueError:
        return 0


def walk_upstream(
    settings: Settings,
    on_repo: Callable[[Path], None] | None = None,
    skip: Callable[[Path], str | None] | None = None,
    on_clean: Callable[[Path], None] | None = None,
) -> Iterator[RepoUpstream]:
    """Yield each repo found behind its upstream, the moment the walk reaches it.

    A generator, not a list, because the walk is the slow part: over a few hundred repos it
    is minutes of ``git fetch``, and collecting them all before the first question means an
    interrupted run answers nothing at all. Yielding hands each repo to the caller while the
    rest are still unfetched. The cost is ordering -- repos arrive in walk order, since
    sorting by how far behind they are would need the whole walk finished first.

    ``on_repo`` is called with each repo path just before it is fetched (progress display);
    a fetch is the slowest thing this tool does, so the walk is worth narrating.

    ``skip`` is handed to ``walk_repos``, which drops a held-back repo before the fetch and
    before the progress line. That is the point of it — held-back repos are the majority on
    a re-run, and fetching them only to drop them again is the whole runtime of the mode.

    ``on_clean`` is called for every repo the fetch settled: up to date, but also the ones
    the question does not apply to (no tracking branch, detached HEAD, unreachable remote).
    Nothing will be asked about them, so recording them here is what stops the next run
    from paying for the same fetch again.
    """
    for repo in walk_repos(settings, on_repo, skip):
        found = measure(repo)
        if found is None:
            if on_clean is not None:
                on_clean(repo)
            continue
        yield found


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


def pull_interactive(settings: Settings, store: MuteStore, prompt_all: bool = False) -> None:
    """Walk the repos this run cares about, asking about each one behind as it is found.

    The menu comes up mid-walk rather than after it: fetching a few hundred repos takes
    minutes, and a run interrupted before the questions started used to leave nothing
    decided and nothing recorded.

    ``prompt_all`` ignores the stored mutes and visits for this run (``--all``), so every
    repo is fetched again — what the walk *records* is unaffected. No-op when stdin is not
    a TTY — there is nothing to prompt.
    """
    if not sys.stdin.isatty():
        print(PULL_NEEDS_TTY)
        return
    # A remote wanting credentials would block the fetch on a console prompt and hang the
    # whole walk. Set for the process rather than threaded through every run_git call.
    os.environ[GIT_TERMINAL_PROMPT_ENV] = GIT_TERMINAL_PROMPT_OFF

    now = time.time()
    skip = (
        None if prompt_all else ScanSkip(store, settings.min_visit_age, now, SKIPPED_WORK_FETCHING)
    )
    found_any = False
    for found in walk_upstream(
        settings,
        on_repo=progress,
        skip=skip,
        # Up to date is a decision the fetch already made, so it counts as a visit even
        # under --all and even if the user aborts the menus below.
        on_clean=lambda repo: store.record_visit(str(repo), now),
    ):
        found_any = True
        clear_progress()
        print(f"\n{found.header()}")
        # Recorded before the menu is drawn, so Abort -- and Ctrl-C, which never returns a
        # choice at all -- still leave the repo recorded: you were shown it, and
        # min_visit_age keeps it out of the next run's fetch.
        store.record_visit(str(found.path), time.time())
        if not prompt_repo(found, store, settings.rename_prefix):
            break

    clear_progress()
    if not found_any:
        print(PULL_NONE_BEHIND)
    report_skipped(skip)
