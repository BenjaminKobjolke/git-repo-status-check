"""The thread a mode runs on, so the window stays responsive while git walks the roots."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .. import runner
from ..app_logger import AppLogger
from ..constants import MENU_ABORTED
from ..frontend import RunCancelled
from ..runner import RunRequest, Stores
from ..settings import Settings, SettingsError


class ModeWorker(QThread):
    """Runs one ``RunRequest`` and reports its exit code; ``execute`` is the testable core."""

    finished_with = Signal(int)

    def __init__(self, settings_path: Path, db_path: Path, request: RunRequest) -> None:
        super().__init__()
        self._settings_path = settings_path
        self._db_path = db_path
        self._request = request

    @property
    def request(self) -> RunRequest:
        return self._request

    def run(self) -> None:
        self.finished_with.emit(self.execute())

    def execute(self) -> int:
        """Load settings, run the mode, translate the two expected failures into a code."""
        settings: Settings | None = None
        if self._request.needs_settings():
            try:
                settings = Settings.load(self._settings_path)
            except SettingsError as exc:
                print(exc)
                return 1
        try:
            return runner.run(settings, Stores.open(self._db_path), self._request)
        except RunCancelled:
            print(MENU_ABORTED)
            return 1
        except Exception as exc:  # noqa: BLE001 -- thread boundary: the window must survive
            AppLogger.error(f"{self._request.mode} failed: {exc!r}")
            return 1
