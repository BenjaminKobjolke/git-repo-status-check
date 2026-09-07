"""The window's ``Frontend``: menus become signals, answers come back through a queue.

The mode loops are synchronous (``choice = menu.choose(...)``) and run on a worker thread.
``choose`` emits what to show and then blocks on a queue; the main thread renders the menu,
the user clicks, ``answer`` puts the value on the queue and the worker resumes. ``cancel``
puts a sentinel instead, and the blocked call raises ``RunCancelled`` -- the Ctrl-C of a
frontend without a console. Child processes are captured line by line and printed, so their
output lands in the log with everything else.
"""

from __future__ import annotations

import queue
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from ..constants import GIT_OUTPUT_ENCODING
from ..frontend import MenuItems, RunCancelled

_CANCEL = object()  # the queue sentinel; never a valid menu answer
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # win32 only: no console flash


class QtFrontend(QObject):
    """Created on the main thread; its methods are called from the worker thread."""

    menu_requested = Signal(list, str)  # [(label, action), ...], title
    text_requested = Signal(str)  # prompt
    progress_changed = Signal(str)  # the repo being scanned; "" once the walk is done

    def __init__(self) -> None:
        super().__init__()
        self._answers: queue.Queue[object] = queue.Queue()
        self._cancelled = False

    # -- Frontend -------------------------------------------------------------------

    def choose(self, items: MenuItems, title: str) -> str:
        self._raise_if_cancelled()
        self.menu_requested.emit([tuple(item) for item in items], title)
        return self._wait()

    def ask_text(self, prompt: str) -> str:
        self._raise_if_cancelled()
        self.text_requested.emit(prompt)
        return self._wait()

    def pause(self) -> None:
        return None  # the log keeps everything on screen; nothing to hold

    def is_interactive(self) -> bool:
        return True

    def progress(self, path: object) -> None:
        self.progress_changed.emit(str(path))

    def clear_progress(self) -> None:
        self.progress_changed.emit("")

    def run_live(self, command: str | tuple[str, ...], cwd: Path, shell: bool = False) -> int:
        """Run the child with its output streamed into the log; return its exit code.

        stdin is closed: a credential prompt cannot be answered from here, so git fails
        fast with its own message instead of hanging the run.
        """
        with subprocess.Popen(
            command,
            shell=shell,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding=GIT_OUTPUT_ENCODING,
            errors="replace",
            creationflags=_NO_WINDOW,
        ) as process:
            assert process.stdout is not None  # PIPE above guarantees it
            for line in process.stdout:
                print(line.rstrip("\r\n"))
            return process.wait()

    # -- main-thread side -------------------------------------------------------------

    @Slot(str)
    def answer(self, value: str) -> None:
        """The user's choice (a menu action value, or typed text)."""
        self._answers.put(value)

    @Slot()
    def cancel(self) -> None:
        """Stop the run at its next question; a blocked question is released now."""
        self._cancelled = True
        self._answers.put(_CANCEL)

    def reset(self) -> None:
        """Forget a previous run's cancel and any answer nobody consumed."""
        self._cancelled = False
        while True:
            try:
                self._answers.get_nowait()
            except queue.Empty:
                return

    def _wait(self) -> str:
        value = self._answers.get()
        if value is _CANCEL:
            raise RunCancelled
        return str(value)

    def _raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise RunCancelled
