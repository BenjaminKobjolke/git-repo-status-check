"""Format and print the scan result. This is program output (print), not logging."""

from __future__ import annotations

import shutil
import sys

from .models import RepoStatus


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


def report(statuses: list[RepoStatus], limit: int | None = None) -> None:
    """Print dirty repos (already sorted newest-first), then a summary line.

    ``limit`` caps the number of printed rows; the summary still reports the true total.
    """
    shown = statuses if limit is None else statuses[:limit]
    for status in shown:
        prefix = "  submodule " if status.is_submodule else ""
        files = "file" if status.dirty_count == 1 else "files"
        print(f"{prefix}{status.path}  -  {status.dirty_count} uncommitted {files}")

    repos = sum(1 for s in statuses if not s.is_submodule)
    suffix = f" (showing {len(shown)})" if limit is not None and len(shown) < len(statuses) else ""
    print(f"\nSummary: {repos} dirty repo(s){suffix}")
