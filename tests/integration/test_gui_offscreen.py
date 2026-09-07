"""Integration tests for the window, rendered offscreen: layout floors, pages, a real run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QTabWidget

from git_repo_status_check import frontend
from git_repo_status_check.constants import COMMIT_MENU
from git_repo_status_check.gui.log_stream import LogStream
from git_repo_status_check.gui.main_window import MainWindow
from git_repo_status_check.gui.qt_frontend import QtFrontend
from git_repo_status_check.gui.worker import ModeWorker
from git_repo_status_check.runner import Mode, RunRequest
from git_repo_status_check.settings_file import SettingsDocument

from .helpers import _init_repo

_TINY = QSize(200, 200)


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[Path, Path]:
    """A settings file pointing at a root with one dirty repo; returns (settings, root)."""
    root = tmp_path / "GIT"
    repo = _init_repo(root / "dirty")
    (repo / "new.txt").write_text("unsaved", encoding="utf-8")
    settings = tmp_path / "settings.json"
    SettingsDocument(folders=[str(root)], commit_command="echo committed").write(settings)
    return settings, root


@pytest.fixture
def log_stream() -> LogStream:
    return LogStream()


@pytest.fixture
def window(
    qt_app: QApplication,
    workspace: tuple[Path, Path],
    log_stream: LogStream,
    monkeypatch: pytest.MonkeyPatch,
) -> MainWindow:
    settings, _ = workspace
    qt_frontend = QtFrontend()
    monkeypatch.setattr(frontend, "_current", qt_frontend)
    built = MainWindow(settings, settings.parent / "mutes.db", qt_frontend, log_stream)
    built.show()
    qt_app.processEvents()
    return built


def test_window_shrinks_to_anything_and_renders_both_tabs(
    qt_app: QApplication, window: MainWindow, tmp_path: Path
) -> None:
    window.resize(_TINY)
    qt_app.processEvents()
    assert window.size().width() <= _TINY.width()
    assert window.size().height() <= _TINY.height()

    window.resize(900, 700)
    tabs = window.centralWidget()
    assert isinstance(tabs, QTabWidget)
    for index, name in enumerate(("run", "settings")):
        tabs.setCurrentIndex(index)
        qt_app.processEvents()
        image = window.grab().toImage()
        assert not image.isNull()
        assert image.save(str(tmp_path / f"{name}.png"))


def test_settings_page_round_trips_and_validates(
    qt_app: QApplication, window: MainWindow, workspace: tuple[Path, Path]
) -> None:
    settings, root = workspace
    page = window.settings_page
    page.add_folder(str(root / "missing"))
    page.save()
    qt_app.processEvents()
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["folders"] == [str(root), str(root / "missing")]
    assert page.message() == "Saved."  # a missing folder is skipped, not an error

    page.load()
    page._min_modified_age.setText("soon")
    page.save()
    assert page.message().startswith("!")
    assert "min_modified_age" in page.message()


def test_scan_runs_on_the_worker_and_lands_in_the_log(
    qt_app: QApplication,
    window: MainWindow,
    workspace: tuple[Path, Path],
    log_stream: LogStream,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _settings, root = workspace
    # What the app does once at startup, done here because pytest re-captures the streams
    # between fixture setup and the test body: print lands in the window.
    monkeypatch.setattr(sys, "stdout", log_stream)
    monkeypatch.setattr(sys, "stderr", log_stream)
    window.start(RunRequest(Mode.SCAN))
    assert window.is_running()
    while window.is_running():
        qt_app.processEvents()
    log = window.run_page.log_text()
    assert str(root / "dirty") in log
    assert "1 uncommitted file" in log
    assert "Finished (exit 0)." in log


def test_commit_ask_renders_the_menu_as_buttons(
    qt_app: QApplication, workspace: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The worker asks; the frontend, pre-fed with Skip, answers -- and the labels match."""
    settings, _ = workspace
    qt_frontend = QtFrontend()
    monkeypatch.setattr(frontend, "_current", qt_frontend)
    asked: list[tuple[list[tuple[str, str]], str]] = []
    qt_frontend.menu_requested.connect(lambda items, title: asked.append((items, title)))
    qt_frontend.answer("s")

    code = ModeWorker(settings, settings.parent / "mutes.db", RunRequest(Mode.COMMIT_ASK)).execute()

    assert code == 0
    assert [items for items, _ in asked] == [list(COMMIT_MENU)]
