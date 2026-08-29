"""Typed return objects — no bag-of-keys dicts crossing module boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoStatus:
    """Uncommitted-changes status for a single git repo (or submodule)."""

    path: Path
    dirty_count: int
    is_submodule: bool = False
    latest_change: float = 0.0  # newest mtime among the uncommitted files (epoch seconds)


@dataclass(frozen=True)
class ChangedFile:
    """One uncommitted file and its on-disk mtime (None if the file is gone)."""

    path: str
    mtime: float | None
    code: str = ""  # the two-character porcelain status (" M", "??", ...)
