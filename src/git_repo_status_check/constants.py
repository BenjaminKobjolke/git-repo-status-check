"""Centralized string/config constants — no raw strings scattered across modules."""

from __future__ import annotations

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

# Porcelain XY codes that can be pure line-ending noise. Every other code (untracked, added,
# deleted, renamed) is a real change and is never filtered.
MODIFIED_ONLY_CODES: frozenset[str] = frozenset({" M", "M ", "MM"})

DEBUG_LINE_ENDING_FILTERED = "{repo}: ignored {count} line-ending-only change(s)"

# --fix-line-endings writes only the repo's local core.autocrlf. `--default ""` makes an unset
# key an empty answer instead of exit code 1, so "unset" and "set to something" read the same way.
GIT_CONFIG_GET_LOCAL_AUTOCRLF: tuple[str, ...] = (
    "config",
    "--local",
    "--get",
    "--default",
    "",
    "core.autocrlf",
)
GIT_CONFIG_SET_AUTOCRLF: tuple[str, ...] = ("config", "core.autocrlf")
GIT_CONFIG_UNSET_AUTOCRLF: tuple[str, ...] = ("config", "--unset", "core.autocrlf")

# Paths with a real content difference left, once the conversion above has been applied. Empty
# output means the file and its blob agree and only the index's cached stat data is stale.
GIT_DIFF_WORKTREE_NAMES: tuple[str, ...] = ("diff", "--name-only", "-z", "--")

# Refreshes that stale stat data. Only ever run on paths the diff above just reported as
# content-identical, so it can never stage an actual change.
GIT_ADD_PATHS: tuple[str, ...] = ("add", "--")

# Values tried, in order. Which one clears the phantom changes depends on whether the blobs
# hold CRLF or LF, so the repair tries and verifies instead of guessing. "true" comes first
# because LF blobs in a CRLF worktree is the common Windows case.
AUTOCRLF_CANDIDATES: tuple[str, ...] = ("true", "false")

# Dirs we never descend into while looking for repos (speed + noise).
NOISE_DIRS: frozenset[str] = frozenset(
    {"node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".ruff_cache"}
)

# settings.json keys.
KEY_FOLDERS = "folders"
KEY_COMMIT_COMMAND = "commit_command"
KEY_IGNORE_PREFIXES = "ignore_prefixes"
KEY_MIN_MODIFIED_AGE = "min_modified_age"
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

# Labels for repos listed but not prompted in --commit-ask (see main.build_skip_reason).
SKIP_LABEL_MUTED = "muted for {duration}"
SKIP_LABEL_RECENT = "changed {duration} ago"

# Interactive commit-loop prompts.
COMMIT_PROMPT = "  [c]ommit / [m]ore / [s]kip / [a]bort? "
COMMIT_PROMPT_HELP = "  Please enter c, m, s, or a."
MORE_PROMPT = "  [a]ge of files / [l]ist files / [p]ull / [e]xplorer / [r]ename / [m]ute / [b]ack? "
MORE_PROMPT_HELP = "  Please enter a, l, p, e, r, m, or b."
MUTE_PROMPT = "  Mute for [1d] / [1w] / [1m] / custom (e.g. 4h, 3d, 2w)? "
MUTE_PROMPT_HELP = "  Please enter a duration like 4h, 1d, 1w, 1m, 3d, or 2w."
EXPLORER_NOT_CONFIGURED = f'  No "{KEY_FILE_EXPLORER}" configured in settings.'
RENAME_PREFIX_NOT_CONFIGURED = f'  No "{KEY_RENAME_PREFIX}" configured in settings.'

# --fix-line-endings prompts and results.
FIX_NEEDS_TTY = "--fix-line-endings needs an interactive terminal; nothing to do."
FIX_NONE_FOUND = "No repos with line-ending-only changes."
FIX_HEADER = "\n{repo}  -  {count} line-ending-only change(s)"
FIX_PROMPT = "  [y]es fix / [n]o skip / [a]bort? "
FIX_PROMPT_HELP = "  Please enter y, n, or a."
FIX_APPLIED = "  OK: core.autocrlf={value} — {count} phantom change(s) gone."
FIX_FAILED = "  FAILED: no core.autocrlf value made it clean (a .gitattributes rule likely wins)."

# Date format for the changed-file age display.
AGE_DATE_FORMAT = "%d.%m.%Y"
