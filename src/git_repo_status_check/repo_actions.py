"""The repo actions the ask-modes share: pull, push, stash, rename, open in explorer.

``--pull-ask`` and the ``--commit-ask`` submenu run the same ones, so they live in one
place — a second copy would be the only way for the two modes to disagree. A module of
their own rather than one mode importing the other: neither ``committer`` nor ``upstream``
depends on the other for them.

User-facing I/O (print) like the modes that call them, not logging.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from . import frontend
from .constants import (
    EXPLORER_NOT_CONFIGURED,
    GIT_CHECKOUT_HEAD_STDIN_PATHS,
    GIT_PULL,
    NUL,
    PULL_LINE_ENDINGS_RESET,
    RENAME_PREFIX_NOT_CONFIGURED,
    REPO_PATH_TOKEN,
    STASH_MESSAGE_FORMAT,
    SUBPROCESS_NO_WINDOW,
)
from .scanner import line_ending_only_paths, run_git


def _run_streaming(path: Path, args: tuple[str, ...], label: str) -> bool:
    """Run ``git <args>`` in the repo dir with live output; report under ``label``.

    Shown live through the frontend (not captured like ``scanner.run_git``) so the user sees
    progress and any credential prompt. Failures surface as-is; the caller decides what to
    offer next.
    """
    code = frontend.get().run_live(("git", "-C", str(path), *args), path)
    if code == 0:
        print(f"  OK ({label}): {path}")
        return True
    print(f"  FAILED ({label}, exit {code}): {path}")
    return False


def run_pull(path: Path) -> bool:
    """``git pull --no-edit`` with live output; True on success.

    The single pull in the codebase — every ask-mode calls this one. ``--no-edit`` because a
    merge commit otherwise opens the git editor over the menu, and the default merge message
    is what would be typed anyway.
    """
    _reset_line_ending_noise(path)
    return _run_streaming(path, GIT_PULL, "pull")


def _reset_line_ending_noise(path: Path) -> None:
    """Restore from HEAD the files whose only change is a CR at end of line.

    The scanner already hides them, so the repo was shown as clean -- but git itself still
    refuses to merge over a file it counts as modified, and on such a repo the menu offers
    no stash either (nothing to stash). Restoring costs nothing: the diff ignoring CR is
    empty for exactly these paths, so only their line endings change, to what a fresh
    checkout under this repo's config would have written anyway. A failed checkout is
    logged by ``run_git``; the pull that follows then fails with git's own message.
    """
    noisy = line_ending_only_paths(path)
    if not noisy:
        return
    run_git(path, GIT_CHECKOUT_HEAD_STDIN_PATHS, input=NUL.join(sorted(noisy)))
    print(PULL_LINE_ENDINGS_RESET.format(count=len(noisy)))


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
    code = frontend.get().run_live(
        ("git", "-C", str(path), "stash", "push", "-u", "-m", message), path
    )
    if code != 0:
        print(f"  FAILED (stash, exit {code}): {path}")
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


def run_explorer(path: Path, command: str | None) -> None:
    """Launch the configured file manager on the repo, detached.

    Fire and forget (``Popen``, not ``subprocess.run``): a file manager stays open for as
    long as the user wants it, so waiting on it would freeze the menu loop.
    """
    if not command:
        print(EXPLORER_NOT_CONFIGURED)
        return
    if REPO_PATH_TOKEN in command:
        launch = command.replace(REPO_PATH_TOKEN, str(path))
    else:
        launch = f'{command} "{path}"'
    subprocess.Popen(launch, shell=True, cwd=str(path), creationflags=SUBPROCESS_NO_WINDOW)
    print(f"  Opened: {path}")
