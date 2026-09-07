"""Every child is started without its own console: under pythonw each git call would
otherwise open and close a cmd window."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import repo_actions, scanner
from git_repo_status_check.constants import SUBPROCESS_NO_WINDOW


def test_run_git_starts_git_without_a_console_window(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def run(command: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs)
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.stdout, result.stderr, result.returncode = "", "", 0
        return result

    monkeypatch.setattr(subprocess, "run", run)
    scanner.run_git(Path("repo"), ("status",))
    assert seen["creationflags"] == SUBPROCESS_NO_WINDOW


def test_explorer_launches_without_a_console_window(mock_popen: MagicMock) -> None:
    # shell=True goes through cmd.exe, which flashes a window of its own under pythonw.
    repo_actions.run_explorer(Path("repo"), "explorer")
    assert mock_popen.call_args.kwargs["creationflags"] == SUBPROCESS_NO_WINDOW
