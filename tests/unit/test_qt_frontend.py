"""Unit tests for the Qt side of the frontend port: queue hand-off, cancel, captured children."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from git_repo_status_check.frontend import RunCancelled
from git_repo_status_check.gui.log_stream import LogStream
from git_repo_status_check.gui.qt_frontend import QtFrontend
from git_repo_status_check.gui.worker import ModeWorker
from git_repo_status_check.runner import Mode, RunRequest


def test_choose_shows_the_menu_and_returns_the_answer() -> None:
    frontend = QtFrontend()
    shown: list[tuple[list[tuple[str, str]], str]] = []
    frontend.menu_requested.connect(lambda items, title: shown.append((items, title)))

    frontend.answer("s")  # pre-fed: on the real thread the click arrives while choose blocks
    assert frontend.choose((("Commit", "c"), ("Skip", "s")), "repo") == "s"
    assert shown == [([("Commit", "c"), ("Skip", "s")], "repo")]


def test_ask_text_returns_the_typed_answer() -> None:
    frontend = QtFrontend()
    frontend.answer("4h")
    assert frontend.ask_text("Duration: ") == "4h"


def test_cancel_releases_a_pending_question_and_refuses_the_next() -> None:
    frontend = QtFrontend()
    frontend.cancel()
    with pytest.raises(RunCancelled):
        frontend.choose((("Yes", "y"),), "title")
    with pytest.raises(RunCancelled):
        frontend.ask_text("prompt")

    frontend.reset()
    frontend.answer("y")
    assert frontend.choose((("Yes", "y"),), "title") == "y"


def test_progress_is_a_signal_and_pause_is_a_no_op() -> None:
    frontend = QtFrontend()
    seen: list[str] = []
    frontend.progress_changed.connect(seen.append)
    frontend.progress(Path("repo"))
    frontend.clear_progress()
    frontend.pause()
    assert seen == [str(Path("repo")), ""]
    assert frontend.is_interactive() is True


def test_run_live_streams_the_child_into_print(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = "import os, sys; print('hello from', os.path.basename(os.getcwd())); sys.exit(3)"
    code = QtFrontend().run_live((sys.executable, "-c", script), tmp_path)
    assert code == 3
    assert f"hello from {tmp_path.name}" in capsys.readouterr().out


def test_log_stream_forwards_text_and_is_not_a_tty() -> None:
    stream = LogStream()
    seen: list[str] = []
    stream.text.connect(seen.append)
    assert stream.write("line\n") == 5
    stream.write("")
    stream.flush()
    assert seen == ["line\n"]
    assert stream.isatty() is False


def test_worker_reports_a_missing_settings_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    worker = ModeWorker(tmp_path / "settings.json", tmp_path / "mutes.db", RunRequest(Mode.SCAN))
    assert worker.execute() == 1
    assert "No settings file" in capsys.readouterr().out


def test_worker_runs_list_muted_without_settings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    worker = ModeWorker(
        tmp_path / "settings.json", tmp_path / "mutes.db", RunRequest(Mode.LIST_MUTED)
    )
    assert worker.execute() == 0
    assert "No muted repos." in capsys.readouterr().out
