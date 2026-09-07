"""The mode orchestration shared by the CLI (``main.py``) and the GUI: which mode runs, over
which stores, and in what order for ``--sync-ask``.

``main.py`` turns arguments into a ``RunRequest``; the GUI builds one from its buttons. Both
hand it to ``run`` so the branch ladder, the commit-command check and the sync stage order
are written once. User-facing output is ``print`` (captured by the GUI), not logging.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from .committer import commit_interactive
from .constants import (
    ASK_REQUIRES_COMMIT_COMMAND,
    FLAG_COMMIT_ASK,
    FLAG_SYNC_ASK,
    MUTED_LINE,
    MUTED_NONE,
    MUTED_SECTION_COMMIT,
    MUTED_SECTION_PULL,
    MUTED_SECTION_PUSH,
    SKIP_LABEL_RECENT,
    SKIPPED_WORK_SCANNING,
    SYNC_STAGE_COMMIT,
    SYNC_STAGE_HEADER,
    SYNC_STAGE_PULL,
    SYNC_STAGE_PUSH,
)
from .duration import format_duration
from .line_endings import fix_interactive
from .models import RepoStatus
from .mute_store import MuteStore, PullMute, PullVisit, PushMute, PushVisit, ScanSkip
from .puller import pull_interactive
from .pusher import push_interactive
from .reporter import clear_progress, progress, report, report_skipped
from .scanner import scan_all
from .settings import Settings


class Mode(StrEnum):
    """One value per way the tool can be run; the CLI flags and the GUI buttons map onto it."""

    SCAN = "scan"
    COMMIT_ASK = "commit-ask"
    PULL_ASK = "pull-ask"
    PUSH_ASK = "push-ask"
    SYNC_ASK = "sync-ask"
    FIX_LINE_ENDINGS = "fix-line-endings"
    LIST_MUTED = "list-muted"


@dataclass(frozen=True)
class RunRequest:
    """What to run and with which switches (``--all``, ``--limit``)."""

    mode: Mode
    prompt_all: bool = False
    limit: int | None = None

    def needs_commit_command(self) -> bool:
        return self.mode in (Mode.COMMIT_ASK, Mode.SYNC_ASK)

    def needs_settings(self) -> bool:
        return self.mode is not Mode.LIST_MUTED


@dataclass(frozen=True)
class Stores:
    """The three ask-modes' mute/visit stores, all on the one ``mutes.db``.

    Opened together rather than per mode: ``--list-muted`` needs every mode's store, and the
    sync mode needs all three in one run.
    """

    commit: MuteStore
    pull: MuteStore
    push: MuteStore

    @classmethod
    def open(cls, db_path: Path) -> Stores:
        return cls(
            commit=MuteStore(db_path),
            pull=MuteStore(db_path, PullMute, PullVisit),
            push=MuteStore(db_path, PushMute, PushVisit),
        )

    def sections(self) -> tuple[tuple[str, MuteStore], ...]:
        """Each store under its ``--list-muted`` heading."""
        return (
            (MUTED_SECTION_COMMIT, self.commit),
            (MUTED_SECTION_PULL, self.pull),
            (MUTED_SECTION_PUSH, self.push),
        )


def run(settings: Settings | None, stores: Stores, request: RunRequest) -> int:
    """Run ``request``; return the process exit code (0 unless a precondition failed).

    ``settings`` may be None only for ``LIST_MUTED``, which never scans.
    """
    if request.mode is Mode.LIST_MUTED:
        _list_muted(stores.sections())
        return 0
    if settings is None:
        raise ValueError(f"{request.mode} needs settings")

    # Repos with nothing but line-ending noise are filtered out of the report entirely,
    # so the repair mode does its own walk instead of running the normal scan first.
    if request.mode is Mode.FIX_LINE_ENDINGS:
        fix_interactive(settings)
        return 0

    # Fail before any walk (a pull walk is minutes) if the commit stage can't be honored.
    if request.needs_commit_command() and not settings.commit_command:
        flag = FLAG_SYNC_ASK if request.mode is Mode.SYNC_ASK else FLAG_COMMIT_ASK
        print(ASK_REQUIRES_COMMIT_COMMAND.format(flag=flag), file=sys.stderr)
        return 1

    if request.mode is Mode.SYNC_ASK:
        _sync_stages(settings, stores, request)
        return 0

    # Being behind a remote is a different question from having uncommitted changes, so this
    # mode does its own walk (it has to fetch) rather than consuming the normal scan.
    if request.mode is Mode.PULL_ASK:
        pull_interactive(settings, stores.pull, prompt_all=request.prompt_all)
        return 0

    # Same shape as --pull-ask, the other way round: commits the upstream lacks.
    if request.mode is Mode.PUSH_ASK:
        push_interactive(settings, stores.push, prompt_all=request.prompt_all)
        return 0

    _commit_stage(settings, stores.commit, request.mode is Mode.COMMIT_ASK, request)
    return 0


def _sync_stages(settings: Settings, stores: Stores, request: RunRequest) -> None:
    """``--sync-ask``: pull, then commit, then push -- each the existing mode, in order.

    The first stage the user aborts ends the run; that stage already printed ``Aborted.``
    so nothing more is said here. Each stage keeps its own store, mutes and visits.
    """
    print(SYNC_STAGE_HEADER.format(stage=SYNC_STAGE_PULL))
    if not pull_interactive(settings, stores.pull, prompt_all=request.prompt_all):
        return
    print(SYNC_STAGE_HEADER.format(stage=SYNC_STAGE_COMMIT))
    if not _commit_stage(settings, stores.commit, True, request):
        return
    print(SYNC_STAGE_HEADER.format(stage=SYNC_STAGE_PUSH))
    push_interactive(settings, stores.push, prompt_all=request.prompt_all)


def _commit_stage(settings: Settings, store: MuteStore, ask: bool, request: RunRequest) -> bool:
    """The scan-and-report, plus the ``--commit-ask`` menus when ``ask``.

    False when the user aborted the menus; True otherwise (plain report mode included).
    """
    # Mutes and visits filter the walk itself, so a held-back repo costs no git call --
    # only --commit-ask acts per repo, so only it filters. --all drops both predicates,
    # which is what makes every repo actionable again.
    now = time.time()
    filtered = ask and not request.prompt_all
    skip = ScanSkip(store, settings.min_visit_age, now, SKIPPED_WORK_SCANNING) if filtered else None

    def record_checked(repo: Path) -> None:
        """Nothing to commit here, so the walk itself settled the repo (see scan_all)."""
        store.record_visit(str(repo), now)

    statuses = scan_all(
        settings,
        on_repo=progress,
        skip=skip,
        # Recorded even under --all: the repo was checked all the same. Plain report mode
        # records nothing -- it is a passive listing, not a decision about any repo.
        on_clean=record_checked if ask else None,
    )
    clear_progress()
    skip_reason = build_skip_reason(settings) if filtered else None
    shown = report(statuses, limit=request.limit, skip_reason=skip_reason)
    report_skipped(skip)

    if not (ask and settings.commit_command):
        return True
    return commit_interactive(
        shown,
        settings.commit_command,
        store,
        settings.file_explorer,
        settings.rename_prefix,
    )


def build_skip_reason(settings: Settings) -> Callable[[RepoStatus], str | None]:
    """Return a predicate labelling repos --commit-ask will not prompt for (None = actionable).

    Only the file-someone-may-still-be-editing test lives here -- the one reason that needs
    the scan's own result. Mutes and menus you already saw are applied a level earlier, at
    the walk (``mute_store.ScanSkip``), so a repo held back for either never reaches this.
    """

    def build(status: RepoStatus) -> str | None:
        # latest_change is 0.0 when no changed file had a readable mtime -- not "1970".
        age = time.time() - status.latest_change
        min_modified_age = settings.min_modified_age
        if min_modified_age is not None and status.latest_change > 0 and age < min_modified_age:
            return SKIP_LABEL_RECENT.format(duration=format_duration(age))
        return None

    return build


def _list_muted(sections: tuple[tuple[str, MuteStore], ...]) -> None:
    """Print every ask-mode's active mutes (soonest expiry first), section by section.

    The modes keep separate mute tables, so listing only one would quietly hide the others.
    """
    now = time.time()
    if not any(source.list_active(now) for _, source in sections):
        print(MUTED_NONE)
        return
    for heading, source in sections:
        print(heading)
        active = source.list_active(now)
        if not active:
            print(f"  {MUTED_NONE}")
            continue
        for record in active:
            local = datetime.fromtimestamp(record.muted_until, tz=UTC).astimezone()
            print(
                "  " + MUTED_LINE.format(path=record.path, until=local.strftime("%Y-%m-%d %H:%M"))
            )
