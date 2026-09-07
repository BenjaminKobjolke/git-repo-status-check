"""Centralized string/config constants — no raw strings scattered across modules."""

from __future__ import annotations

import subprocess

# Marker dirs / files.
GIT_DIR = ".git"
GITMODULES_FILE = ".gitmodules"

# Git subcommands (passed after `git -C <repo>`). `-z` everywhere: it prints raw, unquoted,
# NUL-terminated paths, so the porcelain listing and the diff listings below name a file the
# same way and can be compared. The line-based formats quote spaces and non-ASCII differently
# on each side, which made those paths unmatchable.
GIT_STATUS_PORCELAIN: tuple[str, ...] = ("status", "--porcelain", "-z")

# Files that still differ once a CR at end-of-line is ignored — i.e. the genuinely edited ones.
# With core.autocrlf off, an LF blob checked out as CRLF is "modified" to git although nobody
# touched it; comparing porcelain against these two lists strips that noise out of the count.
GIT_DIFF_WORKTREE_IGNORING_CR: tuple[str, ...] = (
    "diff",
    "--name-only",
    "-z",
    "--ignore-cr-at-eol",
)
GIT_DIFF_STAGED_IGNORING_CR: tuple[str, ...] = (
    "diff",
    "--cached",
    "--name-only",
    "-z",
    "--ignore-cr-at-eol",
)

# Field terminator of every `-z` listing.
NUL = "\0"

# Porcelain codes whose record is followed by a second NUL-terminated field holding the
# rename/copy SOURCE path. R and C can appear in either column (`R `, ` R`, `DR`, ...).
RENAME_COPY_CODES: frozenset[str] = frozenset({"R", "C"})

# git writes path bytes as UTF-8; the process locale must not decide how they decode. cp1252
# (the Windows default here) raises on bytes common in UTF-8 names, which would abort the scan.
# surrogateescape round-trips anything undecodable instead of failing.
GIT_OUTPUT_ENCODING = "utf-8"
GIT_OUTPUT_ERRORS = "surrogateescape"

# win32 only (0 elsewhere): a console-less parent (pythonw) otherwise gets a new console
# window for every console child -- one cmd flash per git call.
SUBPROCESS_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Porcelain XY codes that can be pure line-ending noise. Every other code (untracked, added,
# deleted, renamed) is a real change and is never filtered.
MODIFIED_ONLY_CODES: frozenset[str] = frozenset({" M", "M ", "MM"})

DEBUG_LINE_ENDING_FILTERED = "{repo}: ignored {count} line-ending-only change(s)"

# Remote listing for the submenu's [u]rl key. `-v` is the one form that prints the URLs; it
# names each remote twice (fetch + push), so only the fetch rows are shown.
GIT_REMOTE_VERBOSE: tuple[str, ...] = ("remote", "-v")
GIT_REMOTE_FETCH_SUFFIX = "(fetch)"

# --pull-ask: bring the remote refs up to date, then measure this branch against its upstream.
# `--quiet` because the fetch runs per repo across a whole root and its progress chatter would
# bury the report; failures still surface through run_git.
GIT_FETCH: tuple[str, ...] = ("fetch", "--quiet")
# The tracking branch's name ("origin/main"). Exits non-zero when there is none -- a detached
# HEAD or a branch nobody pushed -- which is exactly how such repos are skipped.
GIT_UPSTREAM_NAME: tuple[str, ...] = (
    "rev-parse",
    "--abbrev-ref",
    "--symbolic-full-name",
    "@{u}",
)
# Prints "<behind>\t<ahead>": commits the upstream has that HEAD lacks, and vice versa. The
# three-dot form is what makes it symmetric; two dots would count only one direction.
GIT_BEHIND_AHEAD: tuple[str, ...] = ("rev-list", "--left-right", "--count", "@{u}...HEAD")
GIT_BEHIND_AHEAD_SEPARATOR = "\t"

# --push-ask on a branch with no upstream: nothing to compare against, so every commit on the
# branch is unpushed and `rev-list --count HEAD` is the ahead count. `symbolic-ref` names the
# branch to push and fails on a detached HEAD, which is how those repos are skipped; `remote`
# lists the remotes the `-u` push could target (first one wins, which is "origin" nearly always).
GIT_CURRENT_BRANCH: tuple[str, ...] = ("symbolic-ref", "--short", "HEAD")
GIT_REMOTES: tuple[str, ...] = ("remote",)
GIT_COMMIT_COUNT: tuple[str, ...] = ("rev-list", "--count", "HEAD")
GIT_PUSH: tuple[str, ...] = ("push",)
# `--no-edit`: a merge commit would otherwise open the git editor over the menu.
GIT_PULL: tuple[str, ...] = ("pull", "--no-edit")
GIT_PUSH_SET_UPSTREAM: tuple[str, ...] = ("push", "-u")

# A remote wanting credentials would otherwise block `git fetch` on a console prompt and hang
# the whole walk. Set once for the process, so no env has to be threaded through run_git.
GIT_TERMINAL_PROMPT_ENV = "GIT_TERMINAL_PROMPT"
GIT_TERMINAL_PROMPT_OFF = "0"

# Run before every pull on the paths `line_ending_only_paths` reports: git refuses to merge
# over a file it sees as modified, even when the only difference is a CR at end of line.
# HEAD rather than the index so a CR-only *staged* diff is cleared too. The paths arrive on
# stdin, NUL-separated (same reason as `-z` everywhere else): no quoting, and no Windows
# command-line length cap for a repo with hundreds of such files.
GIT_CHECKOUT_HEAD_STDIN_PATHS: tuple[str, ...] = (
    "checkout",
    "HEAD",
    "--pathspec-from-file=-",
    "--pathspec-file-nul",
)
PULL_LINE_ENDINGS_RESET = "  Reset {count} line-ending-only file(s) so the pull can proceed."

# Dirs we never descend into while looking for repos (speed + noise).
NOISE_DIRS: frozenset[str] = frozenset(
    {"node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".ruff_cache"}
)

# settings.json keys.
KEY_FOLDERS = "folders"
KEY_COMMIT_COMMAND = "commit_command"
KEY_IGNORE_PREFIXES = "ignore_prefixes"
KEY_MIN_MODIFIED_AGE = "min_modified_age"
KEY_MIN_VISIT_AGE = "min_visit_age"
KEY_FILE_EXPLORER = "file_explorer"
KEY_RENAME_PREFIX = "rename_prefix"

# Placeholder substituted with the repo path in the file_explorer command. Named for the
# value, not generically, so further variables can be added without renaming this one.
REPO_PATH_TOKEN = "[[REPO_PATH]]"

# Environment override for the settings file path.
ENV_SETTINGS_PATH = "GIT_REPO_STATUS_SETTINGS"

# Default settings file name (project root).
DEFAULT_SETTINGS_FILE = "settings.json"
EXAMPLE_SETTINGS_FILE = "settings.example.json"

# Mute database file name (project root, gitignored — machine-local state).
MUTE_DB_FILE = "mutes.db"

# Duration units → seconds. "m" is 30 days (calendar-month approximation), not minutes.
DURATION_UNIT_SECONDS: dict[str, int] = {"h": 3600, "d": 86400, "w": 604800, "m": 2592000}

# Human-readable duration labels, largest first. Sizes come from the parser's table so both
# directions share one definition; "minute" has no parse unit ("m" is month) and lives here only.
DURATION_LABEL_SECONDS: tuple[tuple[str, int], ...] = (
    ("month", DURATION_UNIT_SECONDS["m"]),
    ("week", DURATION_UNIT_SECONDS["w"]),
    ("day", DURATION_UNIT_SECONDS["d"]),
    ("hour", DURATION_UNIT_SECONDS["h"]),
    ("minute", 60),
)
DURATION_BELOW_SMALLEST_UNIT = "less than a minute"

# What an ask-mode reports about the repos it left alone this run (see mute_store.ScanSkip).
# A count rather than a line per repo: on a re-run the held-back repos are most of the walk.
# One template with the work it saved, so both modes word it the same way.
SKIPPED_SUMMARY = (
    "\nSkipped {count} repo(s) without {work} (muted, or seen within min_visit_age). "
    "Pass --all to check them anyway."
)
SKIPPED_WORK_FETCHING = "fetching"
SKIPPED_WORK_SCANNING = "scanning"
SKIPPED_WORK_CHECKING = "checking"
DEBUG_SKIPPED_REPO = "{repo}: not checked ({reason})"

# Labels for repos listed but not prompted in --commit-ask (see main.build_skip_reason).
SKIP_LABEL_MUTED = "muted for {duration}"
SKIP_LABEL_RECENT = "changed {duration} ago"
SKIP_LABEL_VISITED = "seen {duration} ago"

# How long --commit-ask leaves a repo alone after showing its menu, when "min_visit_age" is
# not set. Derived from the unit table so the default and the "1h" a user would type agree.
DEFAULT_MIN_VISIT_AGE_SECONDS = float(DURATION_UNIT_SECONDS["h"])

# Arrow-key menus (see menu.py). Each entry pairs the visible label with the action value
# the caller switches on, so an option can never be shown without a handler behind it.
MENU_INDICATOR = ">"
# Not pick's curses default: a child process that inherits the console kills curses'
# arrow-key translation for the rest of the run (see menu.py).
MENU_BACKEND = "blessed"
MENU_PAUSE_PROMPT = "  Press Enter to continue... "
MENU_NEEDS_TTY = "Menus need a real terminal; this is not a console."
MENU_ABORTED = "Aborted."
# The walk's narration: the repo currently being scanned (one overwritten line / status bar).
PROGRESS_LINE = "Scanning: {path}"

# Checked before any walk starts: a pull walk is minutes, so a missing command fails first.
ASK_REQUIRES_COMMIT_COMMAND = "{flag} requires a non-empty commit_command in settings.json."
FLAG_COMMIT_ASK = "--commit-ask"
FLAG_SYNC_ASK = "--sync-ask"

COMMIT_NEEDS_TTY = "--commit-ask needs an interactive terminal; nothing to do."
COMMIT_HEADER = "{path}  -  {count} uncommitted"
COMMIT_MENU = (
    ("Commit", "c"),
    ("More actions...", "m"),
    ("Skip", "s"),
    ("Abort", "a"),
)
MORE_MENU_TITLE = "{path}  -  more actions"
MORE_MENU = (
    ("Age of changed files", "a"),
    ("List changed files", "l"),
    ("Remote url", "u"),
    ("Pull", "p"),
    ("Open in file explorer", "e"),
    ("Rename repo", "r"),
    ("Stash changes", "s"),
    ("Mute repo", "m"),
    ("Back", "b"),
)
# Stash message, rendered with strftime — a fixed marker so tool-made stashes are recognizable.
STASH_MESSAGE_FORMAT = "%Y_%m_%d GIT REPO STATUS TOOL"
MUTE_CHOICE_CUSTOM = "custom"
MUTE_MENU_TITLE = "Mute this repo for..."
MUTE_MENU = (
    ("1 day", "1d"),
    ("1 week", "1w"),
    ("1 month", "1m"),
    ("Custom duration...", MUTE_CHOICE_CUSTOM),
)
MUTE_CUSTOM_PROMPT = "  Duration (e.g. 4h, 3d, 2w): "
MUTE_PROMPT_HELP = "  Please enter a duration like 4h, 1d, 1w, 1m, 3d, or 2w."
NO_REMOTE_CONFIGURED = "  (no remote)"
EXPLORER_NOT_CONFIGURED = f'  No "{KEY_FILE_EXPLORER}" configured in settings.'
RENAME_PREFIX_NOT_CONFIGURED = f'  No "{KEY_RENAME_PREFIX}" configured in settings.'

# --pull-ask prompts and labels.
PULL_NEEDS_TTY = "--pull-ask needs an interactive terminal; nothing to do."
PULL_NONE_BEHIND = "No repos behind their upstream."
PULL_HEADER = "{path}  -  {behind} commit(s) behind {upstream}"
# Appended to the header when the repo also has local changes: a plain pull can fail on them,
# so the count is a warning, never a filter.
PULL_HEADER_DIRTY = "  -  {count} uncommitted"
PULL_MENU = (
    ("Pull", "p"),
    ("More actions...", "more"),  # not "m": that is Mute here
    ("Skip", "s"),
    ("Mute repo", "m"),
    ("Abort", "a"),
)
# Spliced in after Pull by ``puller.pull_menu``, but only for a repo with local changes:
# the dirty tree is what makes a plain pull fail, so stashing is the way through it. Hidden
# on a clean repo rather than shown and failing -- there would be nothing to stash.
PULL_MENU_STASH = ("Stash changes and pull", "t")
# The --pull-ask submenu (title: MORE_MENU_TITLE): the --commit-ask one minus the entries
# that only make sense for a commit (file ages, list) or sit on the top menu here.
PULL_MORE_MENU = (
    ("Open in file explorer", "e"),
    ("Rename repo", "r"),
    ("Stash changes", "s"),
    ("Back", "b"),
)

# --push-ask prompts and labels. No fetch in this mode, so "ahead" is against the local
# tracking ref; the dirty suffix is PULL_HEADER_DIRTY, shared.
PUSH_NEEDS_TTY = "--push-ask needs an interactive terminal; nothing to do."
PUSH_NONE_AHEAD = "No repos with unpushed commits."
PUSH_HEADER = "{path}  -  {ahead} commit(s) ahead of {upstream}"
PUSH_HEADER_NO_UPSTREAM = "{path}  -  {ahead} commit(s) on {branch}, no upstream"
PUSH_MENU = (
    ("Push", "p"),
    ("Pull", "l"),
    ("Skip", "s"),
    ("Mute repo", "m"),
    ("Abort", "a"),
)
# Replaces the Push label on a branch without upstream, so the menu says what it will run.
PUSH_MENU_SET_UPSTREAM = "Push -u {remote} {branch}"

# --sync-ask: one banner per stage, so the user sees which question is being asked.
SYNC_STAGE_HEADER = "\n=== {stage} ==="
SYNC_STAGE_PULL = "Pull (--pull-ask)"
SYNC_STAGE_COMMIT = "Commit (--commit-ask)"
SYNC_STAGE_PUSH = "Push (--push-ask)"

# --list-muted section headings: the ask-modes keep separate mutes, so each is listed.
MUTED_SECTION_COMMIT = "Commit mutes (--commit-ask):"
MUTED_SECTION_PULL = "Pull mutes (--pull-ask):"
MUTED_SECTION_PUSH = "Push mutes (--push-ask):"
MUTED_NONE = "No muted repos."
MUTED_LINE = "{path}  -  muted until {until}"

# Date format for the changed-file age display.
AGE_DATE_FORMAT = "%d.%m.%Y"
