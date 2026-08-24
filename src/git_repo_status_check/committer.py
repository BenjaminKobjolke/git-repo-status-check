"""Interactive commit loop: ask c/s/a per dirty repo, run the user's commit command.

User-facing I/O (print/input) like reporter.py — not logging. Command invocation lives
here rather than in the git-scanning helper, which only reads repo state.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from .constants import COMMIT_PROMPT, COMMIT_PROMPT_HELP, MUTE_PROMPT, MUTE_PROMPT_HELP
from .duration import parse_duration
from .models import RepoStatus
from .mute_store import MuteStore
from .scanner import _run_git


def commit_interactive(statuses: list[RepoStatus], command: str, store: MuteStore) -> None:
    """Walk ``statuses`` (already sorted/limited), prompting to run ``command`` per repo.

    ``c`` runs the command in the repo dir, ``s`` skips it, ``m`` mutes it for a chosen
    timeframe, ``a`` stops the whole loop. Currently-muted repos are skipped silently.
    No-op when stdin is not a TTY (nothing to prompt).
    """
    if not sys.stdin.isatty():
        print("--commit-ask needs an interactive terminal; nothing to do.")
        return

    for status in statuses:
        if store.is_muted(str(status.path), time.time()):
            continue
        print(f"\n{status.path}  -  {status.dirty_count} uncommitted")
        choice = _ask(status.path)
        if choice == "a":
            print("Aborted.")
            return
        if choice == "s":
            continue
        if choice == "m":
            store.mute(str(status.path), time.time() + _ask_timeframe())
            continue
        _run_commit(command, status)


def _ask(path: Path) -> str:
    """Read a c/m/s/a choice, re-prompting until one is given.

    ``l`` lists the repo's changed files and re-prompts (never returned to the caller).
    """
    while True:
        choice = input(COMMIT_PROMPT).strip().lower()
        if choice == "l":
            _list_files(path)
            continue
        if choice in ("c", "m", "s", "a"):
            return choice
        print(COMMIT_PROMPT_HELP)


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


def _run_commit(command: str, status: RepoStatus) -> None:
    """Run the commit command in the repo dir with live output; report the result."""
    result = subprocess.run(command, shell=True, cwd=str(status.path), check=False)
    if result.returncode == 0:
        print(f"  OK: {status.path}")
    else:
        print(f"  FAILED (exit {result.returncode}): {status.path}")
