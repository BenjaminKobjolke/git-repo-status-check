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
from git_repo_status_check.constants import MUTE_DB_FILE, SKIP_LABEL_MUTED, SKIP_LABEL_RECENT
from git_repo_status_check.duration import format_duration
from git_repo_status_check.line_endings import fix_interactive
from git_repo_status_check.models import RepoStatus
from git_repo_status_check.mute_store import MuteStore
from git_repo_status_check.reporter import clear_progress, progress, report
from git_repo_status_check.scanner import scan_all
from git_repo_status_check.settings import Settings, SettingsError, resolve_settings_path

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
        "--fix-line-endings",
        action="store_true",
        help="Offer to set core.autocrlf per repo whose only changes are line-ending noise.",
    )
    parser.add_argument(
        "--list-muted",
        action="store_true",
        help="List repos currently muted via --commit-ask (and until when), then exit.",
    )
    args = parser.parse_args(argv)

    AppLogger.configure(debug=args.debug)

    store = MuteStore(_PROJECT_ROOT / MUTE_DB_FILE)
    if args.list_muted:
        _list_muted(store)
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

    # Fail before scanning (which can be slow) if --commit-ask can't be honored.
    if args.commit_ask and not settings.commit_command:
        print(
            "--commit-ask requires a non-empty commit_command in settings.json.",
            file=sys.stderr,
        )
        return 1

    # Only --commit-ask acts per repo, so only it needs the skipped ones kept out of --limit.
    skip_reason = build_skip_reason(store, settings.min_modified_age) if args.commit_ask else None
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


def build_skip_reason(
    store: MuteStore, min_modified_age: float | None
) -> Callable[[RepoStatus], str | None]:
    """Return a predicate labelling repos --commit-ask will not prompt for (None = actionable)."""

    def skip_reason(status: RepoStatus) -> str | None:
        now = time.time()
        muted_until = store.muted_until(str(status.path), now)
        if muted_until is not None:
            return SKIP_LABEL_MUTED.format(duration=format_duration(muted_until - now))
        # latest_change is 0.0 when no changed file had a readable mtime -- not "1970".
        age = now - status.latest_change
        if min_modified_age is not None and status.latest_change > 0 and age < min_modified_age:
            return SKIP_LABEL_RECENT.format(duration=format_duration(age))
        return None

    return skip_reason


def _list_muted(store: MuteStore) -> None:
    """Print active mutes (soonest expiry first) with the date each is muted until."""
    active = store.list_active(time.time())
    if not active:
        print("No muted repos.")
        return
    for record in active:
        local = datetime.fromtimestamp(record.muted_until, tz=UTC).astimezone()
        until = local.strftime("%Y-%m-%d %H:%M")
        print(f"{record.path}  -  muted until {until}")


if __name__ == "__main__":
    raise SystemExit(main())
