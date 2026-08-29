"""Locate git repos under configured roots and count their uncommitted changes."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

from .app_logger import AppLogger
from .constants import (
    DEBUG_LINE_ENDING_FILTERED,
    GIT_DIFF_STAGED_IGNORING_CR,
    GIT_DIFF_WORKTREE_IGNORING_CR,
    GIT_DIR,
    GIT_OUTPUT_ENCODING,
    GIT_OUTPUT_ERRORS,
    GIT_STATUS_PORCELAIN,
    GITMODULES_FILE,
    MODIFIED_ONLY_CODES,
    NOISE_DIRS,
    NUL,
    RENAME_COPY_CODES,
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


def run_git(repo: Path, args: tuple[str, ...]) -> str | None:
    """Run ``git -C <repo> <args>``; return stdout, or None if git failed.

    Output is decoded as UTF-8 (git's own path encoding) rather than by the process
    locale, which raises on ordinary non-ASCII names under ``-z``.
    """
    try:
        result = subprocess.run(
            ("git", "-C", str(repo), *args),
            capture_output=True,
            text=True,
            encoding=GIT_OUTPUT_ENCODING,
            errors=GIT_OUTPUT_ERRORS,
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


def _nul_fields(text: str) -> list[str]:
    """Split a ``-z`` listing into its fields; the empty tail after the last NUL is dropped."""
    return [field for field in text.split(NUL) if field]


def _porcelain_records(out: str) -> Iterator[tuple[str, str]]:
    """Yield ``(XY code, path)`` per ``git status --porcelain -z`` record.

    A record is ``XY<space><path>NUL``. Rename/copy records carry the SOURCE path as a
    separate trailing field (``-z`` drops the ``->`` and puts the destination first); it
    belongs to the record before it and is consumed here, never yielded as its own entry.
    Paths arrive verbatim — no quoting, so spaces and non-ASCII need no unescaping.
    """
    fields = _nul_fields(out)
    index = 0
    while index < len(fields):
        record = fields[index]
        index += 1
        if len(record) < 4:  # "XY " plus at least one path character
            continue
        code = record[:2]
        if code[0] in RENAME_COPY_CODES or code[1] in RENAME_COPY_CODES:
            index += 1  # skip the source path trailing this record
        yield code, record[3:]


def _paths_differing_ignoring_cr(repo: Path) -> set[str] | None:
    """Tracked paths that still differ once a CR at end-of-line is ignored (worktree + index).

    None means git failed. The caller must then keep every entry — an unanswered diff read as
    an empty set would hide real changes behind the line-ending filter.
    """
    paths: set[str] = set()
    for args in (GIT_DIFF_WORKTREE_IGNORING_CR, GIT_DIFF_STAGED_IGNORING_CR):
        out = run_git(repo, args)
        if out is None:
            return None
        paths.update(_nul_fields(out))
    return paths


def line_ending_only_paths(
    repo: Path, records: Sequence[tuple[str, str]] | None = None
) -> set[str]:
    """Modified paths whose only difference from the index is a CR at end of line.

    Empty when there is nothing to filter *and* whenever git fails: an unanswered diff must
    never read as "everything was noise". ``records`` lets a caller that already ran
    ``git status`` pass its parsed output instead of paying for a second run.
    """
    if records is None:
        out = run_git(repo, GIT_STATUS_PORCELAIN)
        if out is None:
            return set()
        records = list(_porcelain_records(out))
    candidates = {path for code, path in records if code in MODIFIED_ONLY_CODES}
    if not candidates:
        return set()
    real = _paths_differing_ignoring_cr(repo)
    if real is None:  # run_git already warned; keep everything rather than hide changes.
        return set()
    return candidates - real


def changed_paths(repo: Path) -> set[str]:
    """Every path ``git status`` reports for ``repo``, unfiltered — line-ending noise included.

    The repair in ``line_endings`` needs the raw truth to verify itself; everything else
    wants ``changed_file_ages``.
    """
    out = run_git(repo, GIT_STATUS_PORCELAIN)
    if out is None:
        return set()
    return {path for _, path in _porcelain_records(out)}


def changed_file_ages(repo: Path) -> list[ChangedFile]:
    """Return each uncommitted file with its mtime (None if deleted/inaccessible).

    Modified files whose only difference is a CR at end-of-line are dropped. With
    ``core.autocrlf`` off, an LF blob checked out as CRLF reads as modified although nobody
    edited it, which otherwise flags whole repos as dirty. This is the single place the
    filter is applied — every caller (dirty counts, the commit menu) consumes the filtered
    list.
    """
    out = run_git(repo, GIT_STATUS_PORCELAIN)
    if out is None:
        return []
    records = list(_porcelain_records(out))
    files: list[ChangedFile] = []
    for code, rel in records:
        try:
            mtime: float | None = (repo / rel).stat().st_mtime
        except OSError:
            mtime = None
        files.append(ChangedFile(path=rel, mtime=mtime, code=code))

    noise = line_ending_only_paths(repo, records)
    if not noise:
        return files
    AppLogger.debug(DEBUG_LINE_ENDING_FILTERED.format(repo=repo, count=len(noise)))
    return [f for f in files if f.path not in noise]


def dirty_info(repo: Path) -> tuple[int, float]:
    """Return (uncommitted file count, newest changed-file mtime) for ``repo``.

    Counts every ``git status --porcelain`` record; mtime is the max over the changed files
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
