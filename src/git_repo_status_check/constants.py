"""Centralized string/config constants — no raw strings scattered across modules."""

from __future__ import annotations

# Marker dirs / files.
GIT_DIR = ".git"
GITMODULES_FILE = ".gitmodules"

# Git subcommands (passed after `git -C <repo>`).
GIT_STATUS_PORCELAIN: tuple[str, ...] = ("status", "--porcelain")

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

# Date format for the changed-file age display.
AGE_DATE_FORMAT = "%d.%m.%Y"
