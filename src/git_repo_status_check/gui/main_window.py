"""The main window: the two tabs, the status bar, and the wiring between worker and pages."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import QMainWindow, QScrollArea, QTabWidget, QWidget

from ..runner import RunRequest
from . import window_chrome
from .i18n import TK, t
from .log_stream import LogStream
from .palette import DARK
from .qt_frontend import QtFrontend
from .run_page import MODE_LABELS, RunPage
from .settings_page import SettingsPage
from .worker import ModeWorker

_CLOSE_WAIT_MS = 5000  # how long a closing window waits for a cancelled run to wind down


class MainWindow(QMainWindow):
    def __init__(
        self, settings_path: Path, db_path: Path, frontend: QtFrontend, log: LogStream
    ) -> None:
        super().__init__()
        self._settings_path = settings_path
        self._db_path = db_path
        self._frontend = frontend
        self._worker: ModeWorker | None = None
        self.setWindowTitle(t(TK.WINDOW_TITLE))

        self.run_page = RunPage()
        self.settings_page = SettingsPage(settings_path)
        tabs = QTabWidget()
        tabs.addTab(_scrolling(self.run_page), t(TK.TAB_RUN))
        tabs.addTab(_scrolling(self.settings_page), t(TK.TAB_SETTINGS))
        self.setCentralWidget(tabs)
        self.statusBar().showMessage(t(TK.STATUS_IDLE))

        log.text.connect(self.run_page.append_text)
        frontend.menu_requested.connect(self.run_page.show_menu)
        frontend.text_requested.connect(self.run_page.show_text_prompt)
        frontend.progress_changed.connect(self._show_progress)
        self.run_page.answered.connect(frontend.answer)
        self.run_page.run_requested.connect(self.start)
        self.run_page.stop_requested.connect(self.stop)

    # -- running a mode ---------------------------------------------------------------

    def start(self, request: RunRequest) -> None:
        if self._worker is not None:
            return  # one run at a time; the buttons are disabled meanwhile anyway
        self._frontend.reset()
        label = t(MODE_LABELS[request.mode])
        self.run_page.append_text(t(TK.RUN_STARTED, mode=label) + "\n")
        self.run_page.set_running(True)
        self.statusBar().showMessage(t(TK.STATUS_RUNNING, mode=label))
        self._worker = ModeWorker(self._settings_path, self._db_path, request)
        self._worker.finished_with.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self._worker.start()

    def stop(self) -> None:
        self._frontend.cancel()
        self.statusBar().showMessage(t(TK.STATUS_STOPPING))

    def is_running(self) -> bool:
        return self._worker is not None

    def _finished(self, code: int) -> None:
        self.run_page.append_text(t(TK.RUN_FINISHED, code=code) + "\n")
        self.run_page.set_running(False)
        self.statusBar().showMessage(t(TK.STATUS_IDLE))
        if self._worker is not None:
            self._worker.wait()
            self._worker = None

    def _show_progress(self, path: str) -> None:
        if path:
            self.statusBar().showMessage(t(TK.STATUS_SCANNING, path=path))
        elif self._worker is not None:
            self.statusBar().showMessage(
                t(TK.STATUS_RUNNING, mode=t(MODE_LABELS[self._worker.request.mode]))
            )

    # -- window events ------------------------------------------------------------------

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        window_chrome.apply_dark_titlebar(self, DARK)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None:
            # A run blocked on a question is released now; one inside git ends after it.
            self._frontend.cancel()
            self._worker.wait(_CLOSE_WAIT_MS)
        event.accept()


def _scrolling(page: QWidget) -> QScrollArea:
    """Every tab scrolls: a page's minimum must never become the window's minimum."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(page)
    return area
