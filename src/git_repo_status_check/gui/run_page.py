"""The Run tab: one button per mode, the log, and the prompt panel the menus render into.

The prompt panel is the GUI face of ``menu.choose`` / ``menu.ask_text``: it appears when
the worker asks, its buttons carry the same labels and action values as the terminal menu,
and it disappears the moment an answer goes back.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..runner import Mode, RunRequest
from . import labels, palette, stylesheet
from .i18n import TK, t

# Each mode's button label key, in button order. Scan is the primary action.
MODE_LABELS: dict[Mode, str] = {
    Mode.SCAN: TK.RUN_ACTION_SCAN,
    Mode.COMMIT_ASK: TK.RUN_ACTION_COMMIT_ASK,
    Mode.PULL_ASK: TK.RUN_ACTION_PULL_ASK,
    Mode.PUSH_ASK: TK.RUN_ACTION_PUSH_ASK,
    Mode.SYNC_ASK: TK.RUN_ACTION_SYNC_ASK,
    Mode.FIX_LINE_ENDINGS: TK.RUN_ACTION_FIX_LINE_ENDINGS,
    Mode.LIST_MUTED: TK.RUN_ACTION_LIST_MUTED,
}
_BUTTONS_PER_ROW = 4
_LIMIT_MAX = 999
_LOG_MAX_LINES = 20_000


class RunPage(QWidget):
    """Emits ``run_requested`` with a ``RunRequest``; renders menus; shows the log."""

    run_requested = Signal(object)  # RunRequest
    stop_requested = Signal()
    answered = Signal(str)  # a menu action value, or typed text

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            palette.SPACE_XL, palette.SPACE_XL, palette.SPACE_XL, palette.SPACE_XL
        )
        layout.setSpacing(palette.SPACE_M)
        layout.addWidget(labels.heading(t(TK.RUN_HEADING)))
        layout.addWidget(labels.subheading(t(TK.RUN_SUBHEADING)))
        layout.addSpacing(palette.SPACE_S)

        self._mode_buttons = self._mode_grid(layout)
        self._all, self._limit, self._stop = self._options_row(layout)

        self._log = QPlainTextEdit()
        self._log.setObjectName(stylesheet.LOG)
        self._log.setReadOnly(True)
        self._log.setPlaceholderText(t(TK.RUN_EMPTY))  # the empty state, before any run
        self._log.setMaximumBlockCount(_LOG_MAX_LINES)
        layout.addWidget(self._log, 1)

        self._prompt = self._prompt_panel(layout)
        self._prompt.hide()

    # -- mode buttons ---------------------------------------------------------------

    def _mode_grid(self, layout: QVBoxLayout) -> list[QPushButton]:
        grid = QGridLayout()
        grid.setSpacing(palette.SPACE_S)
        buttons: list[QPushButton] = []
        for index, (mode, key) in enumerate(MODE_LABELS.items()):
            button = QPushButton(t(key))
            if mode is Mode.SCAN:
                button.setObjectName(stylesheet.PRIMARY)
            button.clicked.connect(lambda _checked=False, m=mode: self._request(m))
            grid.addWidget(button, index // _BUTTONS_PER_ROW, index % _BUTTONS_PER_ROW)
            buttons.append(button)
        layout.addLayout(grid)
        return buttons

    def _options_row(self, layout: QVBoxLayout) -> tuple[QCheckBox, QSpinBox, QPushButton]:
        # The checkbox gets a row of its own: its label cannot wrap, and one long line
        # would otherwise set the page's width floor.
        prompt_all = QCheckBox(t(TK.RUN_OPTION_ALL))
        layout.addWidget(prompt_all)
        row = QHBoxLayout()
        row.setSpacing(palette.SPACE_M)
        row.addWidget(labels.hint(t(TK.RUN_OPTION_LIMIT)))
        limit = QSpinBox()
        limit.setRange(0, _LIMIT_MAX)
        limit.setSpecialValueText(t(TK.RUN_OPTION_LIMIT_NONE))  # 0 reads as "no limit"
        row.addWidget(limit)
        row.addStretch()
        stop = QPushButton(t(TK.RUN_ACTION_STOP))
        stop.setEnabled(False)
        stop.clicked.connect(self.stop_requested.emit)
        row.addWidget(stop)
        layout.addLayout(row)
        return prompt_all, limit, stop

    def _request(self, mode: Mode) -> None:
        limit = self._limit.value() or None
        self.run_requested.emit(RunRequest(mode, prompt_all=self._all.isChecked(), limit=limit))

    def set_running(self, running: bool) -> None:
        for button in self._mode_buttons:
            button.setEnabled(not running)
        self._stop.setEnabled(running)
        if not running:
            self.hide_prompt()

    # -- log ------------------------------------------------------------------------

    def append_text(self, text: str) -> None:
        """Print fragments arrive as they are written; keep the view pinned to the end."""
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()

    def log_text(self) -> str:
        return self._log.toPlainText()

    # -- prompt panel ---------------------------------------------------------------

    def _prompt_panel(self, layout: QVBoxLayout) -> QWidget:
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, palette.SPACE_S, 0, 0)
        panel_layout.setSpacing(palette.SPACE_S)
        self._prompt_title = labels.menu_title("")
        panel_layout.addWidget(self._prompt_title)
        self._menu_buttons = QWidget()
        self._menu_layout = QHBoxLayout(self._menu_buttons)
        self._menu_layout.setContentsMargins(0, 0, 0, 0)
        self._menu_layout.setSpacing(palette.SPACE_S)
        panel_layout.addWidget(self._menu_buttons)
        text_row = QHBoxLayout()
        self._text_input = QLineEdit()
        self._text_input.returnPressed.connect(self._submit_text)
        ok = QPushButton(t(TK.PROMPT_OK))
        ok.clicked.connect(self._submit_text)
        text_row.addWidget(self._text_input, 1)
        text_row.addWidget(ok)
        self._text_row = QWidget()
        self._text_row.setLayout(text_row)
        panel_layout.addWidget(self._text_row)
        layout.addWidget(panel)
        return panel

    def show_menu(self, items: list[tuple[str, str]], title: str) -> None:
        self._clear_menu_buttons()
        self._prompt_title.setText(title)
        for label, action in items:
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, a=action: self._answer(a))
            self._menu_layout.addWidget(button)
        self._menu_layout.addStretch()
        self._menu_buttons.show()
        self._text_row.hide()
        self._prompt.show()
        first = self._menu_layout.itemAt(0)
        widget = first.widget() if first is not None else None
        if widget is not None:
            widget.setFocus(Qt.FocusReason.OtherFocusReason)

    def show_text_prompt(self, prompt: str) -> None:
        self._clear_menu_buttons()
        self._prompt_title.setText(prompt)
        self._text_input.clear()
        self._menu_buttons.hide()
        self._text_row.show()
        self._prompt.show()
        self._text_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def hide_prompt(self) -> None:
        self._prompt.hide()

    def menu_labels(self) -> list[str]:
        """The labels currently shown as menu buttons (for tests and the status line)."""
        found: list[str] = []
        for index in range(self._menu_layout.count()):
            item = self._menu_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, QPushButton):
                found.append(widget.text())
        return found

    def _submit_text(self) -> None:
        self._answer(self._text_input.text())

    def _answer(self, value: str) -> None:
        self.hide_prompt()
        self.answered.emit(value)

    def _clear_menu_buttons(self) -> None:
        while self._menu_layout.count():
            item = self._menu_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
