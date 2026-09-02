"""Repair repos whose uncommitted "changes" are nothing but line-ending noise.

The scanner already hides such repos from the report; this is the other half — making git
itself stop reporting them. User-facing I/O (print/input) like committer.py, not logging.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from . import menu
from .constants import (
    AUTOCRLF_CANDIDATES,
    FIX_APPLIED,
    FIX_FAILED,
    FIX_HEADER,
    FIX_MENU,
    FIX_NEEDS_TTY,
    FIX_NONE_FOUND,
    GIT_ADD_PATHS,
    GIT_CONFIG_GET_LOCAL_AUTOCRLF,
    GIT_CONFIG_SET_AUTOCRLF,
    GIT_CONFIG_UNSET_AUTOCRLF,
    GIT_DIFF_WORKTREE_NAMES,
)
from .reporter import clear_progress, progress
from .scanner import changed_paths, line_ending_only_paths, run_git, walk_repos
from .settings import Settings


@dataclass(frozen=True)
class RepairResult:
    """Outcome of one repo's repair. ``autocrlf`` is None when nothing worked."""

    repo: Path
    autocrlf: str | None
    fixed: int

    def message(self) -> str:
        if self.autocrlf is None:
            return FIX_FAILED
        return FIX_APPLIED.format(value=self.autocrlf, count=self.fixed)


def repair(repo: Path, noisy: set[str]) -> RepairResult:
    """Set the repo's local ``core.autocrlf`` so ``noisy`` stops reading as modified.

    Non-destructive: only the repo's own git config and index stat data are written — no
    commit, nothing rewritten on disk, no .gitattributes touched. Which value is right depends
    on whether the committed blobs hold CRLF or LF, and a .gitattributes ``text`` rule can
    outrank the setting entirely, so each candidate is applied and verified against real git
    output rather than guessed. When none of them works the previous value is put back.
    """
    original = _local_autocrlf(repo)
    paths = sorted(noisy)
    for value in AUTOCRLF_CANDIDATES:
        run_git(repo, (*GIT_CONFIG_SET_AUTOCRLF, value))
        # The right conversion alone is not enough: git keeps reporting the files until the
        # index's cached stat data is refreshed ("needs update"), which `git add` does. It is
        # only run once the diff confirms there is no content left to stage.
        if _content_matches(repo, paths):
            run_git(repo, (*GIT_ADD_PATHS, *paths))
            if not changed_paths(repo) & noisy:
                return RepairResult(repo=repo, autocrlf=value, fixed=len(noisy))
    _restore_autocrlf(repo, original)
    return RepairResult(repo=repo, autocrlf=None, fixed=0)


def _content_matches(repo: Path, paths: list[str]) -> bool:
    """True when ``paths`` have no content difference left under the current conversion."""
    out = run_git(repo, (*GIT_DIFF_WORKTREE_NAMES, *paths))
    return out is not None and not out.strip()


def fix_interactive(settings: Settings) -> None:
    """Walk the configured folders and offer to repair every repo with line-ending noise.

    Such repos are invisible to the normal report (the filter empties them), so this mode
    does its own walk instead of consuming ``scan_all``. No-op when stdin is not a TTY.
    """
    if not sys.stdin.isatty():
        print(FIX_NEEDS_TTY)
        return

    found = False
    for repo in walk_repos(settings, progress):
        noisy = line_ending_only_paths(repo)
        if not noisy:
            continue
        clear_progress()
        found = True
        header = FIX_HEADER.format(repo=repo, count=len(noisy))
        print(f"\n{header}")
        choice = menu.choose(FIX_MENU, header)
        if choice == "a":
            return
        if choice == "y":
            print(repair(repo, noisy).message())
    clear_progress()
    if not found:
        print(FIX_NONE_FOUND)


def _local_autocrlf(repo: Path) -> str:
    """The repo's own core.autocrlf value; empty string when it is not set locally."""
    return (run_git(repo, GIT_CONFIG_GET_LOCAL_AUTOCRLF) or "").strip()


def _restore_autocrlf(repo: Path, original: str) -> None:
    if original:
        run_git(repo, (*GIT_CONFIG_SET_AUTOCRLF, original))
    else:
        run_git(repo, GIT_CONFIG_UNSET_AUTOCRLF)
