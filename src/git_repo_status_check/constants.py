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

# Environment override for the settings file path.
ENV_SETTINGS_PATH = "GIT_REPO_STATUS_SETTINGS"

# Default settings file name (project root).
DEFAULT_SETTINGS_FILE = "settings.json"
EXAMPLE_SETTINGS_FILE = "settings.example.json"

# Mute database file name (project root, gitignored — machine-local state).
MUTE_DB_FILE = "mutes.db"

# Mute timeframe units → seconds. "m" is 30 days (calendar-month approximation).
DURATION_UNIT_SECONDS: dict[str, int] = {"d": 86400, "w": 604800, "m": 2592000}

# Interactive commit-loop prompts.
COMMIT_PROMPT = "  [c]ommit / [m]ore / [s]kip / [a]bort? "
COMMIT_PROMPT_HELP = "  Please enter c, m, s, or a."
MORE_PROMPT = "  [a]ge of files / [l]ist files / [p]ull / [m]ute / [b]ack? "
MORE_PROMPT_HELP = "  Please enter a, l, p, m, or b."
MUTE_PROMPT = "  Mute for [1d] / [1w] / [1m] / custom (e.g. 3d, 2w)? "
MUTE_PROMPT_HELP = "  Please enter a duration like 1d, 1w, 1m, 3d, or 2w."

# Date format for the changed-file age display.
AGE_DATE_FORMAT = "%d.%m.%Y"
