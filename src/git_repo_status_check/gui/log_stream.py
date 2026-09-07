"""A ``sys.stdout``/``sys.stderr`` replacement that forwards everything to the log panel.

The modes report with ``print`` and ``AppLogger`` (stderr). Swapping the process streams
once, before anything is configured, is what lets every existing message land in the
window without touching a single call site. Emitting a signal is thread-safe, so a worker
thread can print while the main thread paints.
"""

from __future__ import annotations

import sys
from typing import TextIO, cast

from PySide6.QtCore import QObject, Signal


class LogStream(QObject):
    """File-like enough for ``print`` and ``logging``: ``write``, ``flush``, ``isatty``."""

    text = Signal(str)

    def write(self, data: str) -> int:
        if data:
            self.text.emit(data)
        return len(data)

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False  # keeps the terminal frontend's progress line and any TTY guard off

    def install(self) -> None:
        """Route ``print`` and the logger through this stream for the rest of the process."""
        sys.stdout = cast(TextIO, self)
        sys.stderr = cast(TextIO, self)
