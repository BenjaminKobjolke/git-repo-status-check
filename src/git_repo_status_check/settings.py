"""Central configuration — loads and validates settings.json. No hardcoded roots."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .app_logger import AppLogger
from .constants import (
    DEFAULT_MIN_VISIT_AGE_SECONDS,
    ENV_SETTINGS_PATH,
    EXAMPLE_SETTINGS_FILE,
    KEY_COMMIT_COMMAND,
    KEY_FILE_EXPLORER,
    KEY_FOLDERS,
    KEY_IGNORE_PREFIXES,
    KEY_MIN_MODIFIED_AGE,
    KEY_MIN_VISIT_AGE,
    KEY_RENAME_PREFIX,
    REPO_PATH_TOKEN,
)
from .duration import parse_duration

_EXAMPLE_CONTENT = json.dumps(
    {
        KEY_FOLDERS: ["D:\\GIT"],
        KEY_COMMIT_COMMAND: 'codex --yolo "git commit and push"',
        KEY_FILE_EXPLORER: 'explorer "' + REPO_PATH_TOKEN + '"',
        KEY_IGNORE_PREFIXES: ["_old_"],
        KEY_RENAME_PREFIX: "_old_",
        KEY_MIN_MODIFIED_AGE: "1h",
        KEY_MIN_VISIT_AGE: "1h",
    },
    indent=2,
)


class SettingsError(Exception):
    """Raised when settings.json is missing or invalid — fail fast with a clear message."""


@dataclass(frozen=True)
class Settings:
    """Validated configuration: which root folders to scan."""

    folders: tuple[Path, ...]
    commit_command: str | None = None
    file_explorer: str | None = None
    ignore_prefixes: tuple[str, ...] = ()
    rename_prefix: str | None = None
    min_modified_age: float | None = None
    min_visit_age: float | None = DEFAULT_MIN_VISIT_AGE_SECONDS

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

        commit_command = cls._parse_optional_string(data, path, KEY_COMMIT_COMMAND)
        file_explorer = cls._parse_optional_string(data, path, KEY_FILE_EXPLORER)
        rename_prefix = cls._parse_optional_string(data, path, KEY_RENAME_PREFIX)
        ignore_prefixes = cls._parse_ignore_prefixes(data, path)
        min_modified_age = cls._parse_duration_key(data, path, KEY_MIN_MODIFIED_AGE, None)
        min_visit_age = cls._parse_duration_key(
            data, path, KEY_MIN_VISIT_AGE, DEFAULT_MIN_VISIT_AGE_SECONDS
        )
        return cls(
            folders=tuple(folders),
            commit_command=commit_command,
            file_explorer=file_explorer,
            ignore_prefixes=ignore_prefixes,
            rename_prefix=rename_prefix,
            min_modified_age=min_modified_age,
            min_visit_age=min_visit_age,
        )

    @staticmethod
    def _parse_optional_string(data: dict[str, object], path: Path, key: str) -> str | None:
        """Optional string under ``key`` — absent stays None; present must be non-empty.

        Shared by ``commit_command``, ``file_explorer`` and ``rename_prefix``: same
        contract, same error message.
        """
        if key not in data:
            return None
        value = data[key]
        if not isinstance(value, str) or not value.strip():
            raise SettingsError(f'"{key}" in {path} must be a non-empty string.')
        return value

    @staticmethod
    def _parse_duration_key(
        data: dict[str, object], path: Path, key: str, default: float | None
    ) -> float | None:
        """Optional duration under ``key`` in seconds -- absent falls back to ``default``.

        Shared by ``min_modified_age`` and ``min_visit_age``: same contract, same error
        message. An explicit ``null`` turns the threshold off, which is the only way to do
        so -- ``parse_duration`` rejects ``"0"``. Validated here rather than at use time so
        a typo fails before a slow scan runs.
        """
        if key not in data:
            return default
        value = data[key]
        if value is None:
            return None
        seconds = parse_duration(value) if isinstance(value, str) else None
        if seconds is None:
            raise SettingsError(
                f'"{key}" in {path} must be a duration like "1h", "3d" or "2w" (or null to '
                "turn it off)."
            )
        return seconds

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
