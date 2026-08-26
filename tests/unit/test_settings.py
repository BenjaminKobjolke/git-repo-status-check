"""Unit tests for Settings.load validation and path resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_repo_status_check.constants import ENV_SETTINGS_PATH, EXAMPLE_SETTINGS_FILE
from git_repo_status_check.settings import Settings, SettingsError, resolve_settings_path


def _write_settings(tmp_path: Path, **extra: object) -> Path:
    """Write a settings.json with one existing folder plus any keys under test."""
    folder = tmp_path / "GIT"
    folder.mkdir(exist_ok=True)
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"folders": [str(folder)], **extra}), encoding="utf-8")
    return path


def test_load_valid_settings(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)

    settings = Settings.load(path)
    assert settings.folders == (tmp_path / "GIT",)


def test_load_missing_file_writes_example_and_raises(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    with pytest.raises(SettingsError):
        Settings.load(path)
    assert (tmp_path / EXAMPLE_SETTINGS_FILE).exists()


def test_load_invalid_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(SettingsError):
        Settings.load(path)


def test_load_missing_folders_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"other": []}), encoding="utf-8")
    with pytest.raises(SettingsError):
        Settings.load(path)


def test_load_skips_nonexistent_folders(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"folders": [str(real), str(tmp_path / "ghost")]}), encoding="utf-8")
    settings = Settings.load(path)
    assert settings.folders == (real,)


def test_load_all_folders_missing_raises(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"folders": [str(tmp_path / "ghost")]}), encoding="utf-8")
    with pytest.raises(SettingsError):
        Settings.load(path)


def test_load_reads_commit_command(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, commit_command="do-commit")
    assert Settings.load(path).commit_command == "do-commit"


def test_load_commit_command_absent_is_none(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    assert Settings.load(path).commit_command is None


@pytest.mark.parametrize("bad", ["", "   ", 42, ["x"]])
def test_load_invalid_commit_command_raises(tmp_path: Path, bad: object) -> None:
    path = _write_settings(tmp_path, commit_command=bad)
    with pytest.raises(SettingsError):
        Settings.load(path)


def test_load_ignore_prefixes_absent_is_empty(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    assert Settings.load(path).ignore_prefixes == ()


def test_load_reads_ignore_prefixes(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, ignore_prefixes=["_old_", "tmp_"])
    assert Settings.load(path).ignore_prefixes == ("_old_", "tmp_")


@pytest.mark.parametrize("bad", ["_old_", 42, ["ok", ""], [1], [None]])
def test_load_invalid_ignore_prefixes_raises(tmp_path: Path, bad: object) -> None:
    path = _write_settings(tmp_path, ignore_prefixes=bad)
    with pytest.raises(SettingsError):
        Settings.load(path)


def test_load_min_modified_age_absent_is_none(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    assert Settings.load(path).min_modified_age is None


def test_load_reads_min_modified_age(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, min_modified_age="1h")
    assert Settings.load(path).min_modified_age == 3600.0


@pytest.mark.parametrize("bad", ["", "banana", "0h", "1y", 42, ["1h"]])
def test_load_invalid_min_modified_age_raises(tmp_path: Path, bad: object) -> None:
    path = _write_settings(tmp_path, min_modified_age=bad)
    with pytest.raises(SettingsError):
        Settings.load(path)


def test_resolve_path_prefers_cli(tmp_path: Path) -> None:
    assert resolve_settings_path("custom.json", tmp_path) == Path("custom.json")


def test_resolve_path_uses_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_SETTINGS_PATH, "env.json")
    assert resolve_settings_path(None, tmp_path) == Path("env.json")


def test_resolve_path_defaults_to_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_SETTINGS_PATH, raising=False)
    assert resolve_settings_path(None, tmp_path) == tmp_path / "settings.json"
