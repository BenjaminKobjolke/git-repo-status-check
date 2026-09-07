"""The editable form of ``settings.json`` -- what the GUI reads into its form and writes back.

``Settings.load`` is the validator and is lossy on purpose (missing folders are dropped,
durations become seconds), so a round trip through it would rewrite the user's file. This
document keeps every key as typed. Validation stays with ``Settings.load``: after a save,
the GUI loads the file it just wrote and shows the error, so there is one set of rules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .constants import (
    KEY_COMMIT_COMMAND,
    KEY_FILE_EXPLORER,
    KEY_FOLDERS,
    KEY_IGNORE_PREFIXES,
    KEY_MIN_MODIFIED_AGE,
    KEY_MIN_VISIT_AGE,
    KEY_RENAME_PREFIX,
)
from .settings import EXAMPLE_SETTINGS, Settings, SettingsError


@dataclass
class SettingsDocument:
    """Every settings key as the user typed it. Empty string = key absent on save.

    ``min_visit_age`` has a third state: ``None`` writes JSON ``null``, which is the only way
    to switch that default-on threshold off (see ``Settings._parse_duration_key``).
    """

    folders: list[str] = field(default_factory=list)
    commit_command: str = ""
    file_explorer: str = ""
    rename_prefix: str = ""
    ignore_prefixes: list[str] = field(default_factory=list)
    min_modified_age: str = ""
    min_visit_age: str | None = ""

    @classmethod
    def read(cls, path: Path) -> SettingsDocument:
        """The document at ``path``; the example template when there is no file yet.

        Unreadable JSON is treated like a missing file so the form still opens -- saving
        then overwrites it, which is what the user came to do.
        """
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = EXAMPLE_SETTINGS
        if not isinstance(raw, dict):
            raw = EXAMPLE_SETTINGS
        return cls(
            folders=_strings(raw.get(KEY_FOLDERS)),
            commit_command=_string(raw.get(KEY_COMMIT_COMMAND)),
            file_explorer=_string(raw.get(KEY_FILE_EXPLORER)),
            rename_prefix=_string(raw.get(KEY_RENAME_PREFIX)),
            ignore_prefixes=_strings(raw.get(KEY_IGNORE_PREFIXES)),
            min_modified_age=_string(raw.get(KEY_MIN_MODIFIED_AGE)),
            min_visit_age=None
            if KEY_MIN_VISIT_AGE in raw and raw[KEY_MIN_VISIT_AGE] is None
            else _string(raw.get(KEY_MIN_VISIT_AGE)),
        )

    def to_json(self) -> dict[str, object]:
        """The JSON object to write: optional keys left out when blank."""
        data: dict[str, object] = {KEY_FOLDERS: list(self.folders)}
        for key, value in (
            (KEY_COMMIT_COMMAND, self.commit_command),
            (KEY_FILE_EXPLORER, self.file_explorer),
            (KEY_RENAME_PREFIX, self.rename_prefix),
            (KEY_MIN_MODIFIED_AGE, self.min_modified_age),
        ):
            if value.strip():
                data[key] = value
        if self.ignore_prefixes:
            data[KEY_IGNORE_PREFIXES] = list(self.ignore_prefixes)
        if self.min_visit_age is None:
            data[KEY_MIN_VISIT_AGE] = None
        elif self.min_visit_age.strip():
            data[KEY_MIN_VISIT_AGE] = self.min_visit_age
        return data

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_json(), indent=2) + "\n", encoding="utf-8")


def validate(path: Path) -> str | None:
    """The ``Settings.load`` error for the file at ``path``, or None when it loads.

    The one validator in the codebase, reused: the GUI saves first, then asks this.
    """
    try:
        Settings.load(path)
    except SettingsError as exc:
        return str(exc)
    return None


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, str)]
