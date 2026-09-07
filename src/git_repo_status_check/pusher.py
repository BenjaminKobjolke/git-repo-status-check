"""``--push-ask``: find repos with commits their upstream does not have, and offer to push.

The mirror image of ``--pull-ask``. It borrows that mode's walk and menu loop from
``upstream`` (``walk_found`` / ``ask_interactive``) and only defines what is different: how a
repo is measured, what its header says, and what its menu runs. No fetch -- "ahead" is
measured against the local tracking ref, so the walk is as cheap as the commit-ask scan and
needs no network. A push the remote rejects (it moved on) just brings the menu back, where
*Pull* is one entry away.

User-facing I/O (menus via menu.py, print) like upstream.py, not logging.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from . import menu
from .constants import (
    GIT_BEHIND_AHEAD,
    GIT_COMMIT_COUNT,
    GIT_CURRENT_BRANCH,
    GIT_PUSH,
    GIT_PUSH_SET_UPSTREAM,
    GIT_REMOTES,
    MENU_ABORTED,
    PULL_HEADER_DIRTY,
    PUSH_HEADER,
    PUSH_HEADER_NO_UPSTREAM,
    PUSH_MENU,
    PUSH_MENU_SET_UPSTREAM,
    PUSH_NEEDS_TTY,
    PUSH_NONE_AHEAD,
    SKIPPED_WORK_CHECKING,
)
from .menu import MenuItems
from .mute_store import MuteStore
from .repo_actions import run_pull, run_push
from .scanner import dirty_info, run_git
from .settings import Settings
from .upstream import AskMode, ask_interactive, tracking_branch, upstream_counts


@dataclass(frozen=True)
class RepoAhead:
    """One repo with commits to push, and where they would go."""

    path: Path
    ahead: int
    dirty_count: int  # uncommitted files — shown as a warning, never a filter
    upstream: str | None  # the tracking branch's name; None when the branch has none yet
    branch: str  # the current branch, which is what a first push has to name
    remote: str  # where that first push goes; empty once an upstream exists

    def header(self) -> str:
        """The one line that names this repo, reused as the menu title."""
        if self.upstream is None:
            line = PUSH_HEADER_NO_UPSTREAM.format(
                path=self.path, ahead=self.ahead, branch=self.branch
            )
        else:
            line = PUSH_HEADER.format(path=self.path, ahead=self.ahead, upstream=self.upstream)
        if self.dirty_count:
            line += PULL_HEADER_DIRTY.format(count=self.dirty_count)
        return line

    def push_args(self) -> tuple[str, ...]:
        """The git arguments *Push* runs: derived here so the menu and the action agree."""
        if self.upstream is None:
            return (*GIT_PUSH_SET_UPSTREAM, self.remote, self.branch)
        return GIT_PUSH


def measure_ahead(repo: Path) -> RepoAhead | None:
    """How many commits ``repo`` has that its upstream lacks — None when nothing to push.

    A branch with no upstream is still reported when it has commits and there is a remote to
    push them to (the first one ``git remote`` lists). None also covers every repo the
    question does not apply to: a detached HEAD, an unborn branch, no remote at all. Those are
    ordinary across a folder full of repos, which is why the git calls are made quietly.
    """
    name = tracking_branch(repo)
    if name is not None:
        ahead = upstream_counts(run_git(repo, GIT_BEHIND_AHEAD, quiet=True))[1]
        if ahead <= 0:
            return None
        return RepoAhead(repo, ahead, dirty_info(repo)[0], name, branch="", remote="")

    branch = (run_git(repo, GIT_CURRENT_BRANCH, quiet=True) or "").strip()
    remotes = (run_git(repo, GIT_REMOTES, quiet=True) or "").split()
    ahead = upstream_counts(run_git(repo, GIT_COMMIT_COUNT, quiet=True))[0]
    if not branch or not remotes or ahead <= 0:
        return None
    return RepoAhead(repo, ahead, dirty_info(repo)[0], None, branch=branch, remote=remotes[0])


def push_menu(found: RepoAhead) -> MenuItems:
    """``PUSH_MENU``, reworded for a branch without upstream.

    Built per repo like ``upstream.pull_menu``: the Push entry then names the ``-u`` push it
    will run, and *Pull* is left out — there is no tracking branch to pull from, so it could
    only fail.
    """
    if found.upstream is not None:
        return PUSH_MENU
    label = PUSH_MENU_SET_UPSTREAM.format(remote=found.remote, branch=found.branch)
    return tuple(
        (label if action == "p" else text, action) for text, action in PUSH_MENU if action != "l"
    )


def prompt_repo(found: RepoAhead, store: MuteStore, _settings: Settings) -> bool:
    """Ask about one repo until it is settled; False when the user chose Abort.

    A failed push brings the menu back rather than moving on: the usual cause is a remote
    that moved on, and *Pull* is right there on the same menu.
    """
    while True:
        choice = menu.choose(push_menu(found), found.header())
        if choice == "a":
            print(MENU_ABORTED)
            return False
        if choice == "s":
            return True
        if choice == "m":
            store.mute(str(found.path), time.time() + menu.ask_timeframe())
            return True
        if choice == "l":
            run_pull(found.path)
            menu.pause()
            continue
        pushed = run_push(found.path, found.push_args())
        # The next menu repaints the whole screen, so hold the push output until read.
        menu.pause()
        if pushed:
            return True


PUSH_MODE: AskMode[RepoAhead] = AskMode(
    measure=measure_ahead,
    prompt=prompt_repo,
    needs_tty=PUSH_NEEDS_TTY,
    none_found=PUSH_NONE_AHEAD,
    work=SKIPPED_WORK_CHECKING,
)


def push_interactive(settings: Settings, store: MuteStore, prompt_all: bool = False) -> None:
    """Walk the repos this run cares about, asking about each one ahead as it is found.

    No ``GIT_TERMINAL_PROMPT=0`` here, unlike ``--pull-ask``: nothing runs unattended (the
    measurement is local), and a push may legitimately have to ask for credentials.
    """
    ask_interactive(settings, store, PUSH_MODE, prompt_all)
