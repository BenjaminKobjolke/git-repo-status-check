"""Interactive commit loop: ask c/s/a per dirty repo, run the user's commit command.

User-facing I/O (print/input) like reporter.py — not logging. Command invocation lives
here rather than in the git-scanning helper, which only reads repo state.
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .constants import (
    AGE_DATE_FORMAT,
    COMMIT_PROMPT,
    COMMIT_PROMPT_HELP,
    MORE_PROMPT,
    MORE_PROMPT_HELP,
    MUTE_PROMPT,
    MUTE_PROMPT_HELP,
)
from .duration import parse_duration
from .models import RepoStatus
from .mute_store import MuteStore
from .scanner import _run_git, changed_file_ages


def commit_interactive(statuses: list[RepoStatus], command: str, store: MuteStore) -> None:
    """Walk ``statuses`` (already filtered/limited), prompting to run ``command`` per repo.

    ``c`` runs the command in the repo dir, ``s`` skips it, ``a`` stops the whole loop,
    and ``m`` opens a submenu (age of files / list files / mute). Muting waits for a
    chosen timeframe and skips the repo. Muted and too-recently-changed repos never reach
    here -- the caller filters them out. No-op when stdin is not a TTY (nothing to prompt).
    """
    if not sys.stdin.isatty():
        print("--commit-ask needs an interactive terminal; nothing to do.")
        return

    for status in statuses:
        print(f"\n{status.path}  -  {status.dirty_count} uncommitted")
        choice = _ask(status.path)
        if choice == "a":
            print("Aborted.")
            return
        if choice == "s":
            continue
        if choice == "mute":
            store.mute(str(status.path), time.time() + _ask_timeframe())
            continue
        _run_commit(command, status)


def _ask(path: Path) -> str:
    """Read a top-level c/s/a choice; ``m`` opens the submenu. Returns c/s/a/mute."""
    while True:
        choice = input(COMMIT_PROMPT).strip().lower()
        if choice == "m":
            if _more_menu(path) == "mute":
                return "mute"
            continue  # 'back' — re-show the top prompt
        if choice in ("c", "s", "a"):
            return choice
        print(COMMIT_PROMPT_HELP)


def _more_menu(path: Path) -> str:
    """Submenu: age of files / list files / mute / back. Returns 'mute' or 'back'.

    ``a`` and ``l`` print and re-prompt (they never leave the submenu).
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
        if choice == "m":
            return "mute"
        if choice == "b":
            return "back"
        print(MORE_PROMPT_HELP)


def _list_ages(path: Path) -> None:
    """Print each changed file's date; collapse to one line when all share a date."""
    files = changed_file_ages(path)
    rows = [
        (datetime.fromtimestamp(f.mtime).strftime(AGE_DATE_FORMAT), f.path)
        for f in files
        if f.mtime is not None
    ]
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
    """Print the repo's changed files (git status --short); note when there are none."""
    output = _run_git(path, ("status", "--short"))
    lines = [line for line in (output or "").splitlines() if line.strip()]
    if not lines:
        print("  (no changes)")
        return
    for line in lines:
        print(f"  {line}")


def _run_pull(path: Path) -> None:
    """Run ``git pull`` in the repo dir with live output; report the result.

    Streams like ``_run_commit`` (not captured like ``scanner._run_git``) so the
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
