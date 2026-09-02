"""Interactive commit loop: a menu per dirty repo, running the user's commit command.

User-facing I/O (menus via menu.py, print) like reporter.py — not logging. Command invocation lives
here rather than in the git-scanning helper, which only reads repo state.
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from . import menu, upstream
from .constants import (
    AGE_DATE_FORMAT,
    COMMIT_HEADER,
    COMMIT_MENU,
    COMMIT_NEEDS_TTY,
    EXPLORER_NOT_CONFIGURED,
    GIT_REMOTE_FETCH_SUFFIX,
    GIT_REMOTE_VERBOSE,
    MENU_ABORTED,
    MORE_MENU,
    MORE_MENU_TITLE,
    NO_REMOTE_CONFIGURED,
    RENAME_PREFIX_NOT_CONFIGURED,
    REPO_PATH_TOKEN,
    STASH_MESSAGE_FORMAT,
)
from .models import RepoStatus
from .mute_store import MuteStore
from .scanner import changed_file_ages, run_git


def commit_interactive(
    statuses: list[RepoStatus],
    command: str,
    store: MuteStore,
    file_explorer: str | None = None,
    rename_prefix: str | None = None,
) -> None:
    """Walk ``statuses`` (already filtered/limited), prompting to run ``command`` per repo.

    *Commit* runs the command in the repo dir, *Skip* moves on, *Abort* stops the whole
    loop, and *More actions...* opens a submenu
    (age of files / list files / url / pull / explorer / rename / stash / mute); the pull
    itself is ``upstream.run_pull``, shared with ``--pull-ask``.
    The submenu's explorer entry needs ``file_explorer`` and its rename entry needs
    ``rename_prefix``; without those they report and do nothing.
    Muting asks for a timeframe and skips the repo. Leaving a repo's menu any way but
    Abort records a visit, which holds it back on the next run for ``min_visit_age``.
    Muted, already-visited and too-recently-changed repos never reach here -- the
    caller filters them out. No-op when stdin is not a TTY
    (nothing to prompt).
    """
    if not sys.stdin.isatty():
        print(COMMIT_NEEDS_TTY)
        return

    for status in statuses:
        header = COMMIT_HEADER.format(path=status.path, count=status.dirty_count)
        print(f"\n{header}")
        choice = _ask(header, status.path, file_explorer, rename_prefix)
        if choice == "a":
            print(MENU_ABORTED)
            return
        # Recorded before acting on the choice, so every outcome but Abort counts as a
        # decision about this repo and min_visit_age keeps it quiet on the next run.
        store.record_visit(str(status.path), time.time())
        if choice == "s":
            continue
        if choice == "mute":
            store.mute(str(status.path), time.time() + menu.ask_timeframe())
            continue
        _run_commit(command, status)


def _ask(header: str, path: Path, file_explorer: str | None, rename_prefix: str | None) -> str:
    """Show the per-repo menu; ``m`` opens the submenu. Returns c/s/a/mute.

    ``header`` is the same line printed above the repo, reused as the menu title so the
    repo stays visible while the full-screen menu is up.
    """
    while True:
        choice = menu.choose(COMMIT_MENU, header)
        if choice != "m":
            return choice
        sub = _more_menu(path, file_explorer, rename_prefix)
        if sub == "mute":
            return "mute"
        # Renamed or stashed: nothing left under this path to commit.
        if sub == "skip":
            return "s"
        # 'back' — re-show the top menu.


def _more_menu(path: Path, file_explorer: str | None, rename_prefix: str | None) -> str:
    """Submenu: age / list / url / pull / explorer / rename / stash / mute / back.

    Returns 'mute', 'skip' or 'back'. The read-only actions print and re-prompt (they
    never leave the submenu); so does ``r`` when the rename does not happen. A rename or
    a stash leaves nothing to commit here, so both return 'skip'.
    """
    # Built per call because each closes over this repo's path and the explorer command.
    printing_actions = {
        "a": lambda: _list_ages(path),
        "l": lambda: _list_files(path),
        "u": lambda: _list_remotes(path),
        "p": lambda: upstream.run_pull(path),
        "e": lambda: _open_explorer(file_explorer, path),
    }
    while True:
        choice = menu.choose(MORE_MENU, MORE_MENU_TITLE.format(path=path))
        if choice in printing_actions:
            printing_actions[choice]()
            # The next menu repaints the whole screen, so hold the output until read.
            menu.pause()
            continue
        if choice == "r":
            if _rename_repo(path, rename_prefix):
                return "skip"
            menu.pause()
            continue
        if choice == "s":
            if _run_stash(path):
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


def _run_stash(path: Path) -> bool:
    """Stash the repo's changes (including untracked) under a dated tool message.

    ``-u`` so the stash also clears untracked files — otherwise the repo stays dirty in the
    next scan and the prompt comes straight back. Returns True when the stash succeeded.
    """
    message = datetime.now(tz=UTC).astimezone().strftime(STASH_MESSAGE_FORMAT)
    result = subprocess.run(
        ("git", "-C", str(path), "stash", "push", "-u", "-m", message), check=False
    )
    if result.returncode != 0:
        print(f"  FAILED (stash, exit {result.returncode}): {path}")
        return False
    print(f"  Stashed: {message}")
    return True


def _run_commit(command: str, status: RepoStatus) -> None:
    """Run the commit command in the repo dir with live output; report the result."""
    result = subprocess.run(command, shell=True, cwd=str(status.path), check=False)
    if result.returncode == 0:
        print(f"  OK: {status.path}")
    else:
        print(f"  FAILED (exit {result.returncode}): {status.path}")


def _rename_repo(path: Path, prefix: str | None) -> bool:
    """Rename the repo folder to ``<prefix><name>``; return True when it was renamed.

    The prefix is meant to match one in ``ignore_prefixes`` so the archived folder drops
    out of the next scan. Refuses rather than clobbers when the target already exists.
    """
    if not prefix:
        print(RENAME_PREFIX_NOT_CONFIGURED)
        return False
    if path.name.startswith(prefix):
        print(f"  Already prefixed: {path.name}")
        return False
    target = path.with_name(prefix + path.name)
    if target.exists():
        print(f"  FAILED (rename): {target} already exists.")
        return False
    try:
        path.rename(target)
    except OSError as exc:
        print(f"  FAILED (rename): {exc}")
        return False
    print(f"  Renamed: {path.name} -> {target.name}")
    return True


def _open_explorer(command: str | None, path: Path) -> None:
    """Launch the configured file manager on the repo, detached.

    Fire and forget (``Popen``, not ``subprocess.run``): a file manager stays open for as
    long as the user wants it, so waiting on it would freeze the commit loop.
    """
    if not command:
        print(EXPLORER_NOT_CONFIGURED)
        return
    if REPO_PATH_TOKEN in command:
        launch = command.replace(REPO_PATH_TOKEN, str(path))
    else:
        launch = f'{command} "{path}"'
    subprocess.Popen(launch, shell=True, cwd=str(path))
    print(f"  Opened: {path}")
