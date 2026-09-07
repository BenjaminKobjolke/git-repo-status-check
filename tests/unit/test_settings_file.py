"""Unit tests for the editable settings document: round trip, blank keys, null vs absent."""

from __future__ import annotations

import json
from pathlib import Path

from git_repo_status_check.settings import EXAMPLE_SETTINGS
from git_repo_status_check.settings_file import SettingsDocument, validate


def test_missing_file_reads_as_the_example_template(tmp_path: Path) -> None:
    doc = SettingsDocument.read(tmp_path / "settings.json")
    assert doc.folders == EXAMPLE_SETTINGS["folders"]
    assert doc.commit_command == EXAMPLE_SETTINGS["commit_command"]
    assert doc.min_visit_age == "1h"


def test_round_trip_keeps_every_key_as_typed(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    doc = SettingsDocument(
        folders=["D:\\GIT", "C:/other"],
        commit_command="codex --yolo",
        file_explorer='explorer "[[REPO_PATH]]"',
        rename_prefix="_old_",
        ignore_prefixes=["_old_", "archive_"],
        min_modified_age="4h",
        min_visit_age="2d",
    )
    doc.write(path)
    assert SettingsDocument.read(path) == doc


def test_blank_optional_keys_are_omitted_and_null_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    SettingsDocument(folders=["."], min_visit_age=None).write(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"folders": ["."], "min_visit_age": None}

    doc = SettingsDocument.read(path)
    assert doc.min_visit_age is None  # null: the threshold is switched off
    assert doc.commit_command == ""
    assert doc.ignore_prefixes == []


def test_absent_min_visit_age_stays_absent(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    SettingsDocument(folders=["."]).write(path)
    assert "min_visit_age" not in json.loads(path.read_text(encoding="utf-8"))
    assert SettingsDocument.read(path).min_visit_age == ""


def test_validate_reports_the_settings_error(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    SettingsDocument(folders=[str(tmp_path)], min_modified_age="soon").write(path)
    error = validate(path)
    assert error is not None
    assert "min_modified_age" in error

    SettingsDocument(folders=[str(tmp_path)]).write(path)
    assert validate(path) is None


def test_unreadable_json_falls_back_to_the_template(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    assert SettingsDocument.read(path).folders == EXAMPLE_SETTINGS["folders"]
