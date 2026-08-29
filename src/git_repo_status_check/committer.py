"""Interactive commit loop: ask c/s/a per dirty repo, run the user's commit command.

User-facing I/O (print/input) like reporter.py — not logging. Command invocation lives
here rather than in the git-scanning helper, which only reads repo state.
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from .constants import (
    AGE_DATE_FORMAT,
    COMMIT_PROMPT,
    COMMIT_PROMPT_HELP,
    EXPLORER_NOT_CONFIGURED,
    MORE_PROMPT,
    MORE_PROMPT_HELP,
    MUTE_PROMPT,
    MUTE_PROMPT_HELP,
    RENAME_PREFIX_NOT_CONFIGURED,
    REPO_PATH_TOKEN,
)
from .duration import parse_duration
from .models import RepoStatus
from .mute_store import MuteStore
from .scanner import changed_file_ages


def commit_interactive(
    statuses: list[RepoStatus],
    command: str,
    store: MuteStore,
    file_explorer: str | None = None,
    rename_prefix: str | None = None,
) -> None:
    """Walk ``statuses`` (already filtered/limited), prompting to run ``command`` per repo.

    ``c`` runs the command in the repo dir, ``s`` skips it, ``a`` stops the whole loop,
    and ``m`` opens a submenu (age of files / list files / pull / explorer / rename / mute).
    The submenu's ``e`` needs ``file_explorer`` and its ``r`` needs ``rename_prefix``;
    without those the keys report and do nothing.
    Muting waits for a chosen timeframe and skips the repo. Muted and too-recently-changed
    repos never reach here -- the caller filters them out. No-op when stdin is not a TTY
    (nothing to prompt).
    """
    if not sys.stdin.isatty():
        print("--commit-ask needs an interactive terminal; nothing to do.")
        return

    for status in statuses:
        print(f"\n{status.path}  -  {status.dirty_count} uncommitted")
        choice = _ask(status.path, file_explorer, rename_prefix)
        if choice == "a":
            print("Aborted.")
            return
        if choice == "s":
            continue
        if choice == "mute":
            store.mute(str(status.path), time.time() + _ask_timeframe())
            continue
        _run_commit(command, status)


def _ask(path: Path, file_explorer: str | None, rename_prefix: str | None) -> str:
    """Read a top-level c/s/a choice; ``m`` opens the submenu. Returns c/s/a/mute."""
    while True:
        choice = input(COMMIT_PROMPT).strip().lower()
        if choice == "m":
            sub = _more_menu(path, file_explorer, rename_prefix)
            if sub == "mute":
                return "mute"
            # A renamed repo no longer exists under this path — nothing left to commit.
            if sub == "renamed":
                return "s"
            continue  # 'back' — re-show the top prompt
        if choice in ("c", "s", "a"):
            return choice
        print(COMMIT_PROMPT_HELP)


def _more_menu(path: Path, file_explorer: str | None, rename_prefix: str | None) -> str:
    """Submenu: age / list / pull / explorer / rename / mute / back.

    Returns 'mute', 'renamed' or 'back'. ``a``, ``l``, ``p`` and ``e`` act and re-prompt
    (they never leave the submenu); so does ``r`` when the rename does not happen.
    """
    while True:
        choice = input(MORE_PROMPT).strip().lower()
        if choice == "a":
            _list_ages(path)
            continue
        if choice == "l":
            _list_files(path)
            continue
        if choice == "p":
            _run_pull(path)
            continue
        if choice == "e":
            _open_explorer(file_explorer, path)
            continue
        if choice == "r":
            if _rename_repo(path, rename_prefix):
                return "renamed"
            continue
        if choice == "m":
            return "mute"
        if choice == "b":
            return "back"
        print(MORE_PROMPT_HELP)


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


def _ask_timeframe() -> float:
    """Read a mute timeframe (1d/1w/1m or custom), re-prompting until valid. Returns seconds."""
    while True:
        seconds = parse_duration(input(MUTE_PROMPT))
        if seconds is not None:
            return seconds
        print(MUTE_PROMPT_HELP)


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


def _run_pull(path: Path) -> None:
    """Run ``git pull`` in the repo dir with live output; report the result.

    Streams like ``_run_commit`` (not captured like ``scanner.run_git``) so the
    user sees fetch/merge progress. Plain pull — failures surface as-is.
    """
    result = subprocess.run(("git", "-C", str(path), "pull"), check=False)
    if result.returncode == 0:
        print(f"  OK (pull): {path}")
    else:
        print(f"  FAILED (pull, exit {result.returncode}): {path}")


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
