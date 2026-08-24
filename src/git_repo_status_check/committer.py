"""Interactive commit loop: ask c/s/a per dirty repo, run the user's commit command.

User-facing I/O (print/input) like reporter.py — not logging. Command invocation lives
here rather than in the git-scanning helper, which only reads repo state.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .models import RepoStatus
from .scanner import _run_git

_PROMPT = "  [c]ommit / [l]ist files / [s]kip / [a]bort? "


def commit_interactive(statuses: list[RepoStatus], command: str) -> None:
    """Walk ``statuses`` (already sorted/limited), prompting to run ``command`` per repo.

    ``c`` runs the command in the repo dir, ``s`` skips it, ``a`` stops the whole loop.
    No-op when stdin is not a TTY (nothing to prompt).
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
        _run_commit(command, status)


def _ask(path: Path) -> str:
    """Read a c/s/a choice, re-prompting until one is given.

    ``l`` lists the repo's changed files and re-prompts (never returned to the caller).
    """
    while True:
        choice = input(_PROMPT).strip().lower()
        if choice == "l":
            _list_files(path)
            continue
        if choice in ("c", "s", "a"):
            return choice
        print("  Please enter c, l, s, or a.")


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
