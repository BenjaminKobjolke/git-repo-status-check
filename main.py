"""Entry point: scan configured folders for git repos with uncommitted changes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from git_repo_status_check.app_logger import AppLogger
from git_repo_status_check.constants import MUTE_DB_FILE
from git_repo_status_check.runner import Mode, RunRequest, Stores, run
from git_repo_status_check.settings import Settings, SettingsError, resolve_settings_path

_PROJECT_ROOT = Path(__file__).resolve().parent

# Each mode flag, in the precedence the old branch ladder had: the first one set wins.
_MODE_FLAGS: tuple[tuple[str, Mode], ...] = (
    ("list_muted", Mode.LIST_MUTED),
    ("fix_line_endings", Mode.FIX_LINE_ENDINGS),
    ("sync_ask", Mode.SYNC_ASK),
    ("pull_ask", Mode.PULL_ASK),
    ("push_ask", Mode.PUSH_ASK),
    ("commit_ask", Mode.COMMIT_ASK),
)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    AppLogger.configure(debug=args.debug)

    request = RunRequest(mode=_mode_from(args), prompt_all=args.all, limit=args.limit)
    # All stores are built here, not per branch: --list-muted returns before settings are
    # loaded, so every mode's store has to exist by then to be listed.
    stores = Stores.open(_PROJECT_ROOT / MUTE_DB_FILE)

    settings: Settings | None = None
    if request.needs_settings():
        try:
            settings = Settings.load(resolve_settings_path(args.settings, _PROJECT_ROOT))
        except SettingsError as exc:
            print(exc, file=sys.stderr)
            return 1
    return run(settings, stores, request)


def _mode_from(args: argparse.Namespace) -> Mode:
    for attribute, mode in _MODE_FLAGS:
        if getattr(args, attribute):
            return mode
    return Mode.SCAN


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
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
        "--push-ask",
        action="store_true",
        help="Show a menu for each repo with commits its upstream does not have yet.",
    )
    parser.add_argument(
        "--sync-ask",
        action="store_true",
        help="Run --pull-ask, then --commit-ask, then --push-ask; Abort ends the run.",
    )
    parser.add_argument(
        "--fix-line-endings",
        action="store_true",
        help="Offer to set core.autocrlf per repo whose only changes are line-ending noise.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="With an ask-mode: prompt for every repo, ignoring mutes/visits/recency.",
    )
    parser.add_argument(
        "--list-muted",
        action="store_true",
        help="List repos muted via any ask-mode (and until when), then exit.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
