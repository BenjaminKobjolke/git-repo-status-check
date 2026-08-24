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

# Environment override for the settings file path.
ENV_SETTINGS_PATH = "GIT_REPO_STATUS_SETTINGS"

# Default settings file name (project root).
DEFAULT_SETTINGS_FILE = "settings.json"
EXAMPLE_SETTINGS_FILE = "settings.example.json"
