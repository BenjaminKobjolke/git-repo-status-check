"""Format and print the scan result. This is program output (print), not logging."""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable

from .models import RepoStatus
from .mute_store import ScanSkip


def progress(path: object) -> None:
    """Overwrite one stderr line with the repo currently being scanned (TTY only)."""
    if not sys.stderr.isatty():
        return
    width = shutil.get_terminal_size().columns
    line = f"Scanning: {path}"[: width - 1]
    print(f"\r{line:<{width - 1}}", end="", file=sys.stderr, flush=True)


def clear_progress() -> None:
    """Blank the progress line so it doesn't linger before the report (TTY only)."""
    if not sys.stderr.isatty():
        return
    width = shutil.get_terminal_size().columns
    print(f"\r{'':<{width - 1}}\r", end="", file=sys.stderr, flush=True)


def report_skipped(skip: ScanSkip | None) -> None:
    """Print what a finished walk held back; nothing when the filter was off or idle.

    Both ask-modes end their walk with this line, so the "only if there were any" test lives
    here rather than at each call site.
    """
    summary = skip.summary() if skip is not None else None
    if summary is not None:
        print(summary)


def report(
    statuses: list[RepoStatus],
    limit: int | None = None,
    skip_reason: Callable[[RepoStatus], str | None] | None = None,
) -> list[RepoStatus]:
    """Print dirty repos (already sorted newest-first), then a summary line.

    ``skip_reason`` marks repos that will not be acted on (muted, too fresh); they are still
    printed, labelled with the returned reason, but do not use up a ``limit`` slot -- otherwise
    a screenful of muted repos would leave ``--commit-ask`` with nothing to prompt for.
    Returns the actionable rows so callers (e.g. --commit-ask) reuse the same list.
    """
    actionable: list[RepoStatus] = []
    truncated = False
    for status in statuses:
        reason = skip_reason(status) if skip_reason is not None else None
        if reason is None:
            if limit is not None and len(actionable) >= limit:
                truncated = True
                break
            actionable.append(status)
        prefix = "  submodule " if status.is_submodule else ""
        files = "file" if status.dirty_count == 1 else "files"
        label = f"  [{reason}]" if reason is not None else ""
        print(f"{prefix}{status.path}  -  {status.dirty_count} uncommitted {files}{label}")

    repos = sum(1 for s in statuses if not s.is_submodule)
    shown_repos = sum(1 for s in actionable if not s.is_submodule)
    suffix = f" (showing {shown_repos})" if truncated else ""
    print(f"\nSummary: {repos} dirty repo(s){suffix}")
    return actionable
