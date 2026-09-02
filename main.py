"""Entry point: scan configured folders for git repos with uncommitted changes."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from git_repo_status_check.app_logger import AppLogger
from git_repo_status_check.committer import commit_interactive
from git_repo_status_check.constants import (
    MUTE_DB_FILE,
    MUTED_LINE,
    MUTED_NONE,
    MUTED_SECTION_COMMIT,
    MUTED_SECTION_PULL,
    SKIP_LABEL_RECENT,
    SKIPPED_WORK_SCANNING,
)
from git_repo_status_check.duration import format_duration
from git_repo_status_check.line_endings import fix_interactive
from git_repo_status_check.models import RepoStatus
from git_repo_status_check.mute_store import MuteStore, PullMute, PullVisit, ScanSkip
from git_repo_status_check.reporter import clear_progress, progress, report, report_skipped
from git_repo_status_check.scanner import scan_all
from git_repo_status_check.settings import Settings, SettingsError, resolve_settings_path
from git_repo_status_check.upstream import pull_interactive

_PROJECT_ROOT = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", help="Path to settings.json (default: project root).")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    parser.add_argument("--limit", type=int, help="Show at most N repos (newest changes first).")
    parser.add_argument(
        "--commit-ask",
        action="store_true",
        help="Show a menu per dirty repo and run the settings commit_command on commit.",
    )
    parser.add_argument(
        "--pull-ask",
        action="store_true",
        help="Fetch every repo and show a menu for each one behind its upstream.",
    )
    parser.add_argument(
        "--fix-line-endings",
        action="store_true",
        help="Offer to set core.autocrlf per repo whose only changes are line-ending noise.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="With --commit-ask/--pull-ask: prompt for every repo, ignoring mutes/visits/recency.",
    )
    parser.add_argument(
        "--list-muted",
        action="store_true",
        help="List repos muted via --commit-ask / --pull-ask (and until when), then exit.",
    )
    args = parser.parse_args(argv)

    AppLogger.configure(debug=args.debug)

    # Both stores are built here, not per branch: --list-muted returns before settings are
    # loaded, so the pull store has to exist by then to be listed alongside the commit one.
    store = MuteStore(_PROJECT_ROOT / MUTE_DB_FILE)
    pull_store = MuteStore(_PROJECT_ROOT / MUTE_DB_FILE, PullMute, PullVisit)
    if args.list_muted:
        _list_muted(store, pull_store)
        return 0

    settings_path = resolve_settings_path(args.settings, _PROJECT_ROOT)
    try:
        settings = Settings.load(settings_path)
    except SettingsError as exc:
        print(exc, file=sys.stderr)
        return 1

    # Repos with nothing but line-ending noise are filtered out of the report entirely,
    # so the repair mode does its own walk instead of running the normal scan first.
    if args.fix_line_endings:
        fix_interactive(settings)
        return 0

    # Being behind a remote is a different question from having uncommitted changes, so this
    # mode does its own walk (it has to fetch) rather than consuming the normal scan.
    if args.pull_ask:
        pull_interactive(settings, pull_store, prompt_all=args.all)
        return 0

    # Fail before scanning (which can be slow) if --commit-ask can't be honored.
    if args.commit_ask and not settings.commit_command:
        print(
            "--commit-ask requires a non-empty commit_command in settings.json.",
            file=sys.stderr,
        )
        return 1

    # Mutes and visits filter the walk itself, so a held-back repo costs no git call --
    # only --commit-ask acts per repo, so only it filters. --all drops both predicates,
    # which is what makes every repo actionable again.
    now = time.time()
    ask = args.commit_ask
    skip = (
        ScanSkip(store, settings.min_visit_age, now, SKIPPED_WORK_SCANNING)
        if ask and not args.all
        else None
    )

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
    skip_reason = build_skip_reason(settings) if ask and not args.all else None
    shown = report(statuses, limit=args.limit, skip_reason=skip_reason)
    report_skipped(skip)

    if args.commit_ask and settings.commit_command:
        commit_interactive(
            shown,
            settings.commit_command,
            store,
            settings.file_explorer,
            settings.rename_prefix,
        )
    return 0


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


def _list_muted(store: MuteStore, pull_store: MuteStore) -> None:
    """Print both ask-modes' active mutes (soonest expiry first), section by section.

    The modes keep separate mute tables, so listing only one would quietly hide the other.
    """
    now = time.time()
    sections = ((MUTED_SECTION_COMMIT, store), (MUTED_SECTION_PULL, pull_store))
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


if __name__ == "__main__":
    raise SystemExit(main())
