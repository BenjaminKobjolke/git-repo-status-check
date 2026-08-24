"""Central configuration — loads and validates settings.json. No hardcoded roots."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .app_logger import AppLogger
from .constants import (
    ENV_SETTINGS_PATH,
    EXAMPLE_SETTINGS_FILE,
    KEY_COMMIT_COMMAND,
    KEY_FOLDERS,
    KEY_IGNORE_PREFIXES,
)

_EXAMPLE_CONTENT = json.dumps(
    {KEY_FOLDERS: ["D:\\GIT"], KEY_COMMIT_COMMAND: "", KEY_IGNORE_PREFIXES: ["_old_"]},
    indent=2,
)


class SettingsError(Exception):
    """Raised when settings.json is missing or invalid — fail fast with a clear message."""


@dataclass(frozen=True)
class Settings:
    """Validated configuration: which root folders to scan."""

    folders: tuple[Path, ...]
    commit_command: str | None = None
    ignore_prefixes: tuple[str, ...] = ()

    @classmethod
    def load(cls, path: Path) -> Settings:
        """Read and validate settings from ``path``.

        Raises ``SettingsError`` (with a message telling the user what to fix) when the
        file is missing, unparsable, or does not contain a list of existing directories.
        """
        if not path.exists():
            example = path.with_name(EXAMPLE_SETTINGS_FILE)
            example.write_text(_EXAMPLE_CONTENT, encoding="utf-8")
            raise SettingsError(
                f"No settings file at {path}. Wrote a template to {example} — "
                f"copy it to {path.name} and set your folders."
            )

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SettingsError(f"{path} is not valid JSON: {exc}") from exc

        if not isinstance(data, dict) or KEY_FOLDERS not in data:
            raise SettingsError(f'{path} must be a JSON object with a "{KEY_FOLDERS}" key.')

        raw_folders = data[KEY_FOLDERS]
        if not isinstance(raw_folders, list) or not raw_folders:
            raise SettingsError(f'"{KEY_FOLDERS}" in {path} must be a non-empty list of paths.')

        folders: list[Path] = []
        for entry in raw_folders:
            if not isinstance(entry, str):
                raise SettingsError(f'"{KEY_FOLDERS}" entries must be strings, got: {entry!r}')
            folder = Path(entry)
            if not folder.is_dir():
                AppLogger.warning(f"Configured folder does not exist, skipping: {folder}")
                continue
            folders.append(folder)

        if not folders:
            raise SettingsError(f"None of the configured folders in {path} exist.")

        commit_command = cls._parse_commit_command(data, path)
        ignore_prefixes = cls._parse_ignore_prefixes(data, path)
        return cls(
            folders=tuple(folders),
            commit_command=commit_command,
            ignore_prefixes=ignore_prefixes,
        )

    @staticmethod
    def _parse_commit_command(data: dict[str, object], path: Path) -> str | None:
        """Optional ``commit_command`` — absent stays None; present must be a non-empty string."""
        if KEY_COMMIT_COMMAND not in data:
            return None
        value = data[KEY_COMMIT_COMMAND]
        if not isinstance(value, str) or not value.strip():
            raise SettingsError(f'"{KEY_COMMIT_COMMAND}" in {path} must be a non-empty string.')
        return value

    @staticmethod
    def _parse_ignore_prefixes(data: dict[str, object], path: Path) -> tuple[str, ...]:
        """Optional ``ignore_prefixes`` — absent stays empty; folders whose name starts
        with any prefix are skipped during scanning. Must be a list of non-empty strings."""
        if KEY_IGNORE_PREFIXES not in data:
            return ()
        value = data[KEY_IGNORE_PREFIXES]
        if not isinstance(value, list):
            raise SettingsError(f'"{KEY_IGNORE_PREFIXES}" in {path} must be a list of strings.')
        prefixes: list[str] = []
        for entry in value:
            if not isinstance(entry, str) or not entry:
                raise SettingsError(
                    f'"{KEY_IGNORE_PREFIXES}" entries must be non-empty strings, got: {entry!r}'
                )
            prefixes.append(entry)
        return tuple(prefixes)


def resolve_settings_path(cli_path: str | None, project_root: Path) -> Path:
    """Pick the settings path: --settings > env var > project-root default."""
    if cli_path:
        return Path(cli_path)
    env = os.getenv(ENV_SETTINGS_PATH)
    if env:
        return Path(env)
    from .constants import DEFAULT_SETTINGS_FILE

    return project_root / DEFAULT_SETTINGS_FILE
