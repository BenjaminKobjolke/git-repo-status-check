"""Locate git repos under configured roots and count their uncommitted changes."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

from .app_logger import AppLogger
from .constants import (
    GIT_DIR,
    GIT_STATUS_PORCELAIN,
    GITMODULES_FILE,
    NOISE_DIRS,
)
from .models import ChangedFile, RepoStatus
from .settings import Settings


def find_repos(root: Path, ignore_prefixes: tuple[str, ...] = ()) -> Iterator[Path]:
    """Yield each git repo under ``root``, not descending into a repo once found.

    Directories whose name starts with any of ``ignore_prefixes`` are pruned from the
    walk (case-sensitive). An empty tuple prunes nothing.
    """
    for dirpath, dirnames, _files in os.walk(root):
        current = Path(dirpath)
        if (current / GIT_DIR).exists():
            yield current
            dirnames[:] = []  # stop descending into a repo
            continue
        dirnames[:] = [
            d for d in dirnames if d not in NOISE_DIRS and not d.startswith(ignore_prefixes)
        ]


def _run_git(repo: Path, args: tuple[str, ...]) -> str | None:
    """Run ``git -C <repo> <args>``; return stdout, or None if git failed."""
    try:
        result = subprocess.run(
            ("git", "-C", str(repo), *args),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        AppLogger.error("git executable not found on PATH.")
        return None
    if result.returncode != 0:
        stderr = result.stderr.strip()
        # .git can exist yet be unreadable (dead gitlink/worktree pointer, empty dir).
        # Warn cleanly instead of dumping the raw fatal; the repo is skipped either way.
        if "not a git repository" in stderr:
            AppLogger.warning(f"{repo}: .git present but not a valid git repository — skipping")
        else:
            AppLogger.warning(f"git {' '.join(args)} failed in {repo}: {stderr}")
        return None
    return result.stdout


def _porcelain_path(line: str) -> str:
    """Extract the file path from a porcelain line (cols 3+), resolving rename arrows."""
    path = line[3:]
    if " -> " in path:  # rename/copy: "old -> new" — the new path is what exists on disk
        path = path.split(" -> ", 1)[1]
    return path.strip().strip('"')


def changed_file_ages(repo: Path) -> list[ChangedFile]:
    """Return each uncommitted file with its mtime (None if deleted/inaccessible)."""
    out = _run_git(repo, GIT_STATUS_PORCELAIN)
    if out is None:
        return []
    files: list[ChangedFile] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        rel = _porcelain_path(line)
        try:
            mtime: float | None = (repo / rel).stat().st_mtime
        except OSError:
            mtime = None
        files.append(ChangedFile(path=rel, mtime=mtime))
    return files


def dirty_info(repo: Path) -> tuple[int, float]:
    """Return (uncommitted file count, newest changed-file mtime) for ``repo``.

    Counts every ``git status --porcelain`` line; mtime is the max over the changed files
    that still exist on disk (deleted files are skipped). Empty repo → (0, 0.0).
    """
    files = changed_file_ages(repo)
    latest = max((f.mtime for f in files if f.mtime is not None), default=0.0)
    return len(files), latest


def _submodule_paths(repo: Path) -> list[Path]:
    """Return submodule paths declared in ``repo``'s .gitmodules (empty if none).

    Parses the file directly instead of ``git submodule status``: the latter aborts the
    whole listing when .gitmodules is inconsistent with the index (a gitlink whose path
    has no mapping — "no submodule mapping found in .gitmodules"). The declared ``path =``
    lines are the source of truth for what the repo intends to be a submodule.
    """
    gitmodules = repo / GITMODULES_FILE
    try:
        text = gitmodules.read_text(encoding="utf-8")
    except OSError:
        return []
    paths: list[Path] = []
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "path":
            sub = value.strip()
            if sub:
                paths.append(repo / sub)
    return paths


def scan_repo(repo: Path) -> list[RepoStatus]:
    """Status for ``repo`` and each of its submodules; only dirty entries returned."""
    statuses: list[RepoStatus] = []
    count, latest = dirty_info(repo)
    if count > 0:
        statuses.append(RepoStatus(path=repo, dirty_count=count, latest_change=latest))

    if (repo / GITMODULES_FILE).exists():
        for sub in _submodule_paths(repo):
            if not (sub / GIT_DIR).exists():
                continue  # submodule not initialized/checked out — nothing to scan
            sub_count, sub_latest = dirty_info(sub)
            if sub_count > 0:
                statuses.append(
                    RepoStatus(
                        path=sub,
                        dirty_count=sub_count,
                        is_submodule=True,
                        latest_change=sub_latest,
                    )
                )
    return statuses


def scan_all(settings: Settings, on_repo: Callable[[Path], None] | None = None) -> list[RepoStatus]:
    """Scan every configured root; return dirty repos + submodules, newest change first.

    ``on_repo`` is called with each repo path just before it is scanned (progress display).
    """
    results: list[RepoStatus] = []
    for root in settings.folders:
        AppLogger.debug(f"Scanning {root}")
        for repo in find_repos(root, settings.ignore_prefixes):
            if on_repo is not None:
                on_repo(repo)
            results.extend(scan_repo(repo))
    results.sort(key=lambda s: s.latest_change, reverse=True)
    return results
