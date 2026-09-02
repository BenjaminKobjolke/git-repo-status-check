"""``--pull-ask``: fetch every repo under the configured roots and offer to pull stale ones.

The normal report only ever asks the working tree, so a repo that is clean but sitting
behind its remote is invisible to it. This is the other direction — it asks the remote.
Self-contained like ``line_endings.py`` (its own walk, its own report, its own menu)
because it selects repos on a criterion the shared scan never computes.

User-facing I/O (menus via menu.py, print) like committer.py, not logging.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import menu
from .app_logger import AppLogger
from .constants import (
    DEBUG_PULL_SKIPPED,
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
    PULL_NEEDS_TTY,
    PULL_NONE_BEHIND,
    PULL_SKIPPED_SUMMARY,
)
from .mute_store import MuteStore, skip_reason
from .reporter import clear_progress, progress
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


def scan_upstream(
    settings: Settings,
    on_repo: Callable[[Path], None] | None = None,
    skip: Callable[[Path], str | None] | None = None,
) -> list[RepoUpstream]:
    """Walk every configured root and return the repos behind upstream, most stale first.

    ``on_repo`` is called with each repo path just before it is fetched (progress display);
    a fetch is the slowest thing this tool does, so the walk is worth narrating.

    ``skip`` is consulted **before** the fetch: a repo it names a reason for costs no
    network at all. That is the point of it — held-back repos are the majority on a re-run,
    and fetching them only to drop them again is the whole runtime of the mode.
    """
    results: list[RepoUpstream] = []
    for repo in walk_repos(settings, on_repo):
        if skip is not None and skip(repo) is not None:
            continue
        found = measure(repo)
        if found is not None:
            results.append(found)
    results.sort(key=lambda r: r.behind, reverse=True)
    return results


def report_upstream(results: list[RepoUpstream]) -> None:
    """Print each repo that is behind. Everything listed here will be prompted for.

    No skip labels, unlike ``reporter.report``: repos this run holds back are filtered out
    before the fetch, so there is no state to report about them.
    """
    if not results:
        print(PULL_NONE_BEHIND)
        return
    for found in results:
        print(found.header())


def run_pull(path: Path) -> None:
    """Run ``git pull`` in the repo dir with live output; report the result.

    Streams (not captured like ``scanner.run_git``) so the user sees fetch/merge progress.
    Plain pull — failures surface as-is. The single pull in the codebase: the
    ``--commit-ask`` submenu calls this one too.
    """
    result = subprocess.run(("git", "-C", str(path), "pull"), check=False)
    if result.returncode == 0:
        print(f"  OK (pull): {path}")
    else:
        print(f"  FAILED (pull, exit {result.returncode}): {path}")


def pull_interactive(settings: Settings, store: MuteStore, prompt_all: bool = False) -> None:
    """Fetch the repos this run cares about, report the ones behind, and prompt for each.

    ``prompt_all`` ignores the stored mutes and visits for this run (``--all``), so every
    repo is fetched again. No-op when stdin is not a TTY — there is nothing to prompt.
    """
    if not sys.stdin.isatty():
        print(PULL_NEEDS_TTY)
        return
    # A remote wanting credentials would block the fetch on a console prompt and hang the
    # whole walk. Set for the process rather than threaded through every run_git call.
    os.environ[GIT_TERMINAL_PROMPT_ENV] = GIT_TERMINAL_PROMPT_OFF

    now = time.time()
    skipped = 0

    def skip(repo: Path) -> str | None:
        nonlocal skipped
        reason = skip_reason(store, str(repo), now, settings.min_visit_age)
        if reason is not None:
            skipped += 1
            AppLogger.debug(DEBUG_PULL_SKIPPED.format(repo=repo, reason=reason))
        return reason

    results = scan_upstream(settings, on_repo=progress, skip=None if prompt_all else skip)
    clear_progress()
    report_upstream(results)
    # A count, not a line per repo: on a re-run the held-back repos are most of the walk.
    if skipped:
        print(PULL_SKIPPED_SUMMARY.format(count=skipped))

    for found in results:
        print(f"\n{found.header()}")
        choice = menu.choose(PULL_MENU, found.header())
        if choice == "a":
            print(MENU_ABORTED)
            return
        # Recorded before acting, so every outcome but Abort counts as a decision about this
        # repo and min_visit_age keeps it out of the next run's fetch entirely.
        store.record_visit(str(found.path), time.time())
        if choice == "s":
            continue
        if choice == "m":
            store.mute(str(found.path), time.time() + menu.ask_timeframe())
            continue
        run_pull(found.path)
        # The next menu repaints the whole screen, so hold the pull output until read.
        menu.pause()
