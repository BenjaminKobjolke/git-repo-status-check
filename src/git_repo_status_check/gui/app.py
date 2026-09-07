"""GUI entry point: streams, logger, theme, frontend, window -- in that order.

The log stream is installed before the logger is configured so ``AppLogger``'s handler
binds to it; the Qt frontend is installed before the window so the first run finds it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .. import frontend
from ..app_logger import AppLogger
from ..constants import MUTE_DB_FILE
from ..settings import resolve_settings_path
from . import i18n, theme
from .log_stream import LogStream
from .main_window import MainWindow
from .qt_frontend import QtFrontend

LANG_DIR_NAME = "lang"
_INITIAL_SIZE = (960, 720)  # a starting size only; the window shrinks to anything


def main(project_root: Path, argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    log = LogStream()
    log.install()
    AppLogger.configure(debug=args.debug)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    assert isinstance(app, QApplication)
    theme.apply_dark(app)
    i18n.configure(project_root / LANG_DIR_NAME)
    qt_frontend = QtFrontend()
    frontend.install(qt_frontend)

    window = MainWindow(
        resolve_settings_path(args.settings, project_root),
        project_root / MUTE_DB_FILE,
        qt_frontend,
        log,
    )
    window.resize(*_INITIAL_SIZE)
    window.show()
    return app.exec()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", help="Path to settings.json (default: project root).")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args(argv)
