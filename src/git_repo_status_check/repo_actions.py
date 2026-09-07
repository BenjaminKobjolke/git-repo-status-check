"""The repo actions the ask-modes share: pull, push, stash, rename.

``--pull-ask`` and the ``--commit-ask`` submenu run the same three, so they live in one
place — a second copy would be the only way for the two modes to disagree. A module of
their own rather than one mode importing the other: neither ``committer`` nor ``upstream``
depends on the other for them.

User-facing I/O (print) like the modes that call them, not logging.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .constants import GIT_PULL, RENAME_PREFIX_NOT_CONFIGURED, STASH_MESSAGE_FORMAT


def _run_streaming(path: Path, args: tuple[str, ...], label: str) -> bool:
    """Run ``git <args>`` in the repo dir with live output; report under ``label``.

    Streams (not captured like ``scanner.run_git``) so the user sees progress and any
    credential prompt. Failures surface as-is; the caller decides what to offer next.
    """
    result = subprocess.run(("git", "-C", str(path), *args), check=False)
    if result.returncode == 0:
        print(f"  OK ({label}): {path}")
        return True
    print(f"  FAILED ({label}, exit {result.returncode}): {path}")
    return False


def run_pull(path: Path) -> bool:
    """``git pull --no-edit`` with live output; True on success.

    The single pull in the codebase — every ask-mode calls this one. ``--no-edit`` because a
    merge commit otherwise opens the git editor over the menu, and the default merge message
    is what would be typed anyway.
    """
    return _run_streaming(path, GIT_PULL, "pull")


def run_push(path: Path, push_args: tuple[str, ...]) -> bool:
    """``git <push_args>`` with live output; True on success.

    ``push_args`` comes from ``RepoAhead.push_args`` -- a plain push, or ``push -u`` with the
    remote and branch when the branch has no upstream yet.
    """
    return _run_streaming(path, push_args, "push")


def run_stash(path: Path) -> bool:
    """Stash the repo's changes (including untracked) under a dated tool message.

    ``-u`` so the stash also clears untracked files — otherwise the repo stays dirty and the
    same prompt comes straight back. Returns True when the stash succeeded.

    Both ask-modes run it: ``--pull-ask`` to clear the way for a pull, the ``--commit-ask``
    submenu to put a repo aside.
    """
    message = datetime.now(tz=UTC).astimezone().strftime(STASH_MESSAGE_FORMAT)
    result = subprocess.run(
        ("git", "-C", str(path), "stash", "push", "-u", "-m", message), check=False
    )
    if result.returncode != 0:
        print(f"  FAILED (stash, exit {result.returncode}): {path}")
        return False
    print(f"  Stashed: {message}")
    return True


def run_rename(path: Path, prefix: str | None) -> bool:
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
