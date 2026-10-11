"""Interactive commit loop: a menu per dirty repo, running the user's commit command.

User-facing I/O (menus via menu.py, print) like reporter.py — not logging. Command invocation lives
here rather than in the git-scanning helper, which only reads repo state.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from . import frontend, menu, repo_actions
from .commit_constants import (
    COMMIT_MESSAGE_EMPTY,
    COMMIT_MESSAGE_PROMPT,
    COMMIT_NO_PUSH_TARGET,
)
from .constants import (
    AGE_DATE_FORMAT,
    COMMIT_HEADER,
    COMMIT_MENU,
    COMMIT_NEEDS_TTY,
    GIT_REMOTE_FETCH_SUFFIX,
    GIT_REMOTE_VERBOSE,
    MENU_ABORTED,
    MORE_MENU,
    MORE_MENU_TITLE,
    NO_REMOTE_CONFIGURED,
)
from .menu import MenuItems
from .models import RepoStatus
from .mute_store import MuteStore
from .pusher import measure_ahead
from .scanner import changed_file_ages, run_git


def commit_interactive(
    statuses: list[RepoStatus],
    command: str | None,
    store: MuteStore,
    file_explorer: str | None = None,
    rename_prefix: str | None = None,
) -> bool:
    """Walk ``statuses`` and offer configured, typed-message and TortoiseGit commits.

    Returns False when the user chose Abort (so ``--sync-ask`` can end the whole run), True
    once every repo was settled -- or there was nothing to prompt.

    When ``command`` is None, only the typed-message and TortoiseGit entries are shown.
    *Skip* moves on, *Abort* stops the whole
    loop, and *More actions...* opens a submenu
    (age of files / list files / url / pull / explorer / rename / stash / mute); the pull,
    the explorer, the stash and the rename come from ``repo_actions``, shared with
    ``--pull-ask``.
    The submenu's explorer entry needs ``file_explorer`` and its rename entry needs
    ``rename_prefix``; without those they report and do nothing.
    Muting asks for a timeframe and skips the repo. Showing a repo's menu records a visit,
    which holds it back on the next run for ``min_visit_age`` -- Abort and Ctrl-C included,
    since you were shown the repo either way.
    Muted, already-visited and too-recently-changed repos never reach here -- the
    caller filters them out. No-op when stdin is not a TTY
    (nothing to prompt).
    """
    if not menu.is_interactive():
        print(COMMIT_NEEDS_TTY)
        return True

    for status in statuses:
        header = COMMIT_HEADER.format(path=status.path, count=status.dirty_count)
        print(f"\n{header}")
        # Recorded before the menu is drawn, so Abort -- and Ctrl-C, which never returns a
        # choice at all -- still leave the repo recorded: you were shown it, and
        # min_visit_age keeps it quiet on the next run. Repos further down the list are
        # untouched: you never saw those.
        store.record_visit(str(status.path), time.time())
        while True:
            choice = _ask(header, status.path, file_explorer, rename_prefix, commit_menu(command))
            if choice == "a":
                print(MENU_ABORTED)
                return False
            if choice == "s":
                break
            if choice == "mute":
                store.mute(str(status.path), time.time() + menu.ask_timeframe())
                break
            if choice == "c":
                _run_commit(command, status, shell=True)
                break
            if choice == "g":
                _run_commit(
                    ("TortoiseGitProc.exe", "/command:commit", f"/path:{status.path}"), status
                )
                break
            if _commit_typed(status.path):
                break
            menu.pause()
    return True


def commit_menu(command: str | None) -> MenuItems:
    """Return the commit menu, omitting the configured-command action when absent."""
    return COMMIT_MENU if command else tuple(item for item in COMMIT_MENU if item[1] != "c")


def _ask(
    header: str,
    path: Path,
    file_explorer: str | None,
    rename_prefix: str | None,
    items: MenuItems,
) -> str:
    """Show the per-repo menu; ``m`` opens the submenu. Returns a top-menu action.

    ``header`` is the same line printed above the repo, reused as the menu title so the
    repo stays visible while the full-screen menu is up.
    """
    while True:
        choice = menu.choose(items, header)
        if choice != "m":
            return choice
        sub = _more_menu(path, file_explorer, rename_prefix)
        if sub == "mute":
            return "mute"
        # Renamed or stashed: nothing left under this path to commit.
        if sub == "skip":
            return "s"
        # 'back' — re-show the top menu.


def _commit_typed(path: Path) -> bool:
    """Commit one typed message and push it when the branch has a push target."""
    message = menu.ask_text(COMMIT_MESSAGE_PROMPT).strip()
    if not message:
        print(COMMIT_MESSAGE_EMPTY)
        return False
    if not repo_actions.run_commit(path, message):
        return False
    found = measure_ahead(path)
    if found is None:
        print(COMMIT_NO_PUSH_TARGET)
    elif not repo_actions.run_push(path, found.push_args()):
        menu.pause()
    return True


def _more_menu(path: Path, file_explorer: str | None, rename_prefix: str | None) -> str:
    """Submenu: age / list / url / pull / explorer / rename / stash / mute / back.

    Returns 'mute', 'skip' or 'back'. The read-only actions print and re-prompt (they
    never leave the submenu); so does ``r`` when the rename does not happen. A rename or
    a stash leaves nothing to commit here, so both return 'skip'.
    """
    # Built per call because each closes over this repo's path and the explorer command.
    printing_actions: dict[str, Callable[[], object]] = {
        "a": lambda: _list_ages(path),
        "l": lambda: _list_files(path),
        "u": lambda: _list_remotes(path),
        "p": lambda: repo_actions.run_pull(path),
        "e": lambda: repo_actions.run_explorer(path, file_explorer),
    }
    while True:
        choice = menu.choose(MORE_MENU, MORE_MENU_TITLE.format(path=path))
        if choice in printing_actions:
            printing_actions[choice]()
            # The next menu repaints the whole screen, so hold the output until read.
            menu.pause()
            continue
        if choice == "r":
            if repo_actions.run_rename(path, rename_prefix):
                return "skip"
            menu.pause()
            continue
        if choice == "s":
            if repo_actions.run_stash(path):
                return "skip"
            menu.pause()
            continue
        return "mute" if choice == "m" else "back"


def format_age_date(mtime: float) -> str:
    """Format a file mtime as a local-time date.

    Read as UTC then converted to local rather than a naive ``fromtimestamp``: same
    result, but the timezone is stated instead of implied (ruff DTZ006).
    """
    return datetime.fromtimestamp(mtime, tz=UTC).astimezone().strftime(AGE_DATE_FORMAT)


def _list_ages(path: Path) -> None:
    """Print each changed file's date; collapse to one line when all share a date."""
    files = changed_file_ages(path)
    rows = [(format_age_date(f.mtime), f.path) for f in files if f.mtime is not None]
    if not rows:
        print("  (no dated files)")
        return
    labels = {date for date, _ in rows}
    if len(rows) == len(files) and len(labels) == 1:
        print(f"  All {len(rows)} files: {next(iter(labels))}")
    else:
        for date, file_path in rows:
            print(f"  {date}  {file_path}")


def _list_files(path: Path) -> None:
    """Print the repo's changed files; note when there are none.

    Reuses ``changed_file_ages`` rather than its own git call so the listing is exactly the
    set that was counted — line-ending-only entries are absent from both.
    """
    files = changed_file_ages(path)
    if not files:
        print("  (no changes)")
        return
    for changed in files:
        print(f"  {changed.code} {changed.path}")


def _list_remotes(path: Path) -> None:
    """Print each remote's name and fetch URL; note when the repo has none.

    Captured via ``run_git`` (not streamed like ``_run_pull``) so the push duplicates
    ``git remote -v`` prints can be dropped before display.
    """
    output = run_git(path, GIT_REMOTE_VERBOSE) or ""
    # Split on the tab, not on whitespace: a local-path remote may contain spaces.
    rows = [
        line.removesuffix(GIT_REMOTE_FETCH_SUFFIX).split("\t", 1)
        for line in output.splitlines()
        if line.endswith(GIT_REMOTE_FETCH_SUFFIX)
    ]
    if not rows:
        print(NO_REMOTE_CONFIGURED)
        return
    for row in rows:
        print("  " + "  ".join(part.strip() for part in row))


def _run_commit(command: str | tuple[str, ...], status: RepoStatus, shell: bool = False) -> None:
    """Run the commit command in the repo dir with live output; report the result."""
    code = frontend.get().run_live(command, status.path, shell=shell)
    if code == 0:
        print(f"  OK: {status.path}")
    else:
        print(f"  FAILED (exit {code}): {status.path}")
