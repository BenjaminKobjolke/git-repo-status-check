"""Entry point: scan configured folders for git repos with uncommitted changes."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from git_repo_status_check.app_logger import AppLogger
from git_repo_status_check.committer import commit_interactive
from git_repo_status_check.constants import MUTE_DB_FILE
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
        help="Prompt c/l/m/s/a per dirty repo and run the settings commit_command on commit.",
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

    # Fail before scanning (which can be slow) if --commit-ask can't be honored.
    if args.commit_ask and not settings.commit_command:
        print(
            "--commit-ask requires a non-empty commit_command in settings.json.",
            file=sys.stderr,
        )
        return 1

    statuses = scan_all(settings, on_repo=progress)
    clear_progress()
    shown = report(statuses, limit=args.limit)

    if args.commit_ask and settings.commit_command:
        commit_interactive(shown, settings.commit_command, store)
    return 0


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
