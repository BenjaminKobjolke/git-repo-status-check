"""The ``--pull-ask`` measurement, and the walk-and-ask loop it shares with ``--push-ask``.

The normal report only ever asks the working tree, so a repo that is clean but sitting
behind its remote is invisible to it. This is the other direction — it asks the remote.
It does its own walk because it selects repos on a criterion the shared scan never
computes. ``--push-ask`` asks the same question the other way round, so the walk
(``walk_found``) and the menu loop (``ask_interactive``) are written here once over an
``AskMode``, and each mode (``puller``, ``pusher``) supplies only its measurement, its
prompt and its wording.

User-facing I/O (menus via menu.py, print) like committer.py, not logging.
"""

from __future__ import annotations

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
    GIT_UPSTREAM_NAME,
    PULL_HEADER,
    PULL_HEADER_DIRTY,
)
from .mute_store import MuteStore, ScanSkip
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


def ask_interactive(
    settings: Settings, store: MuteStore, mode: AskMode[T], prompt_all: bool = False
) -> bool:
    """Walk the repos this run cares about, asking about each one ``mode`` finds as it is found.

    Returns False when the user chose Abort, so ``--sync-ask`` can end the whole run; True
    once the walk ran to its end (nothing found, or no TTY, counts as completed).

    The menu comes up mid-walk rather than after it: fetching a few hundred repos takes
    minutes, and a run interrupted before the questions started used to leave nothing
    decided and nothing recorded.

    ``prompt_all`` ignores the stored mutes and visits for this run (``--all``), so every
    repo is measured again — what the walk *records* is unaffected. No-op when stdin is not
    a TTY — there is nothing to prompt.
    """
    if not menu.is_interactive():
        print(mode.needs_tty)
        return True

    now = time.time()
    skip = None if prompt_all else ScanSkip(store, settings.min_visit_age, now, mode.work)
    found_any = False
    completed = True
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
            completed = False
            break

    clear_progress()
    if not found_any:
        print(mode.none_found)
    report_skipped(skip)
    return completed
