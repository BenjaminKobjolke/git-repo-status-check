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
)
from git_repo_status_check.duration import format_duration
from git_repo_status_check.line_endings import fix_interactive
from git_repo_status_check.models import RepoStatus
from git_repo_status_check.mute_store import MuteStore, PullMute, PullVisit, skip_reason
from git_repo_status_check.reporter import clear_progress, progress, report
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

    # Only --commit-ask acts per repo, so only it needs the skipped ones kept out of --limit.
    # --all drops the predicate entirely, which is what makes every repo actionable again.
    skip_reason = build_skip_reason(store, settings) if args.commit_ask and not args.all else None
    statuses = scan_all(settings, on_repo=progress)
    clear_progress()
    shown = report(statuses, limit=args.limit, skip_reason=skip_reason)

    if args.commit_ask and settings.commit_command:
        commit_interactive(
            shown,
            settings.commit_command,
            store,
            settings.file_explorer,
            settings.rename_prefix,
        )
    return 0


def build_skip_reason(store: MuteStore, settings: Settings) -> Callable[[RepoStatus], str | None]:
    """Return a predicate labelling repos --commit-ask will not prompt for (None = actionable).

    Reasons are checked most-deliberate first, so the label names the strongest one: an
    explicit mute, then a menu you already saw (both shared with ``--pull-ask`` via
    ``mute_store.skip_reason``), then a file someone may still be editing -- the one test
    only this mode has.
    """

    def build(status: RepoStatus) -> str | None:
        now = time.time()
        shared = skip_reason(store, str(status.path), now, settings.min_visit_age)
        if shared is not None:
            return shared
        # latest_change is 0.0 when no changed file had a readable mtime -- not "1970".
        age = now - status.latest_change
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
