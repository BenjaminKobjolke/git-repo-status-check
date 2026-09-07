"""``--pull-ask``, and the walk-and-ask loop it shares with ``--push-ask``.

The normal report only ever asks the working tree, so a repo that is clean but sitting
behind its remote is invisible to it. This is the other direction — it asks the remote.
It does its own walk (its own measurement, its own menu) because it selects repos on a
criterion the shared scan never computes. ``--push-ask`` asks the same question the other way
round, so the walk (``walk_found``) and the menu loop (``ask_interactive``) are written here
once over an ``AskMode``, and each mode supplies only its measurement, its prompt and its
wording.

User-facing I/O (menus via menu.py, print) like committer.py, not logging.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, Protocol, TypeVar

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


class Found(Protocol):
    """What the shared loop needs from a repo a mode found: where it is, and its headline."""

    @property
    def path(self) -> Path: ...

    def header(self) -> str: ...


T = TypeVar("T", bound=Found)


@dataclass(frozen=True)
class AskMode(Generic[T]):
    """Everything that differs between ``--pull-ask`` and ``--push-ask``, in one object.

    ``measure`` decides whether a repo is worth asking about (None = nothing to ask);
    ``prompt`` settles one found repo and returns False on Abort. The strings are the mode's
    wording for the no-TTY notice, the nothing-found line and the skipped-summary ``work``.
    """

    measure: Callable[[Path], T | None]
    prompt: Callable[[T, MuteStore, Settings], bool]
    needs_tty: str
    none_found: str
    work: str


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


def tracking_branch(repo: Path) -> str | None:
    """The name of ``repo``'s tracking branch ("origin/main"), or None when it has none.

    None covers a detached HEAD and a branch nobody pushed — ordinary across a folder full of
    repos, which is why the call is made quietly.
    """
    return (run_git(repo, GIT_UPSTREAM_NAME, quiet=True) or "").strip() or None


def measure(repo: Path) -> RepoUpstream | None:
    """Fetch ``repo``, then report how far behind its upstream it is — None when it is not.

    None also covers every repo the question simply does not apply to: no tracking branch,
    a detached HEAD, an unreachable remote.
    """
    run_git(repo, GIT_FETCH, quiet=True)
    name = tracking_branch(repo)
    if name is None:
        return None
    behind = upstream_counts(run_git(repo, GIT_BEHIND_AHEAD, quiet=True))[0]
    if behind <= 0:
        return None
    return RepoUpstream(
        path=repo,
        upstream=name,
        behind=behind,
        dirty_count=dirty_info(repo)[0],
    )


def upstream_counts(out: str | None) -> tuple[int, int]:
    """``(behind, ahead)`` from ``rev-list --left-right --count``'s ``<behind><TAB><ahead>``.

    ``(0, 0)`` whenever the answer is missing or malformed: one bad line must drop its own
    repo, never abort the walk over all the others. Also reads a lone ``rev-list --count``
    number (no tab) as ``(count, 0)``, which is how ``--push-ask`` counts a branch with no
    upstream.
    """
    if out is None:
        return 0, 0
    first, _, second = out.strip().partition(GIT_BEHIND_AHEAD_SEPARATOR)
    try:
        return int(first), int(second or 0)
    except ValueError:
        return 0, 0


def walk_found(
    settings: Settings,
    measure_repo: Callable[[Path], T | None],
    on_repo: Callable[[Path], None] | None = None,
    skip: Callable[[Path], str | None] | None = None,
    on_clean: Callable[[Path], None] | None = None,
) -> Iterator[T]:
    """Yield each repo ``measure_repo`` reports, the moment the walk reaches it.

    A generator, not a list, because the walk is the slow part: over a few hundred repos a
    pull walk is minutes of ``git fetch``, and collecting them all before the first question
    means an interrupted run answers nothing at all. The cost is ordering -- repos arrive in
    walk order, since sorting would need the whole walk finished first.

    ``on_repo`` narrates the walk (progress display). ``skip`` is handed to ``walk_repos``,
    which drops a held-back repo before the measurement and the progress line -- held-back
    repos are the majority on a re-run, and measuring them only to drop them again would be
    the whole runtime of the mode. ``on_clean`` is called for every repo the measurement
    settled (nothing to do, or the question does not apply); nothing will be asked about
    them, so recording them is what stops the next run from measuring them again.
    """
    for repo in walk_repos(settings, on_repo, skip):
        found = measure_repo(repo)
        if found is None:
            if on_clean is not None:
                on_clean(repo)
            continue
        yield found


def walk_upstream(
    settings: Settings,
    on_repo: Callable[[Path], None] | None = None,
    skip: Callable[[Path], str | None] | None = None,
    on_clean: Callable[[Path], None] | None = None,
) -> Iterator[RepoUpstream]:
    """``walk_found`` over the pull measurement: each repo found behind its upstream."""
    return walk_found(settings, measure, on_repo, skip, on_clean)


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


def ask_interactive(
    settings: Settings, store: MuteStore, mode: AskMode[T], prompt_all: bool = False
) -> None:
    """Walk the repos this run cares about, asking about each one ``mode`` finds as it is found.

    The menu comes up mid-walk rather than after it: fetching a few hundred repos takes
    minutes, and a run interrupted before the questions started used to leave nothing
    decided and nothing recorded.

    ``prompt_all`` ignores the stored mutes and visits for this run (``--all``), so every
    repo is measured again — what the walk *records* is unaffected. No-op when stdin is not
    a TTY — there is nothing to prompt.
    """
    if not sys.stdin.isatty():
        print(mode.needs_tty)
        return

    now = time.time()
    skip = None if prompt_all else ScanSkip(store, settings.min_visit_age, now, mode.work)
    found_any = False
    for found in walk_found(
        settings,
        mode.measure,
        on_repo=progress,
        skip=skip,
        # Nothing to do is a decision the measurement already made, so it counts as a visit
        # even under --all and even if the user aborts the menus below.
        on_clean=lambda repo: store.record_visit(str(repo), now),
    ):
        found_any = True
        clear_progress()
        print(f"\n{found.header()}")
        # Recorded before the menu is drawn, so Abort -- and Ctrl-C, which never returns a
        # choice at all -- still leave the repo recorded: you were shown it, and
        # min_visit_age keeps it out of the next run's walk.
        store.record_visit(str(found.path), time.time())
        if not mode.prompt(found, store, settings):
            break

    clear_progress()
    if not found_any:
        print(mode.none_found)
    report_skipped(skip)


def pull_interactive(settings: Settings, store: MuteStore, prompt_all: bool = False) -> None:
    """``ask_interactive`` in pull mode, with git's credential prompt switched off first.

    A remote wanting credentials would block the fetch on a console prompt and hang the
    whole walk. Set for the process rather than threaded through every run_git call.
    """
    os.environ[GIT_TERMINAL_PROMPT_ENV] = GIT_TERMINAL_PROMPT_OFF
    ask_interactive(settings, store, PULL_MODE, prompt_all)
