"""The single hook that turns a plain ``QApplication`` into the themed one."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from . import stylesheet
from .palette import DARK

FUSION_STYLE = "Fusion"  # the native Windows style ignores the colour scheme on some builds


def apply_dark(app: QApplication) -> None:
    """Fusion + dark colour scheme + the one stylesheet. Safe on an already-styled app."""
    app.setStyle(FUSION_STYLE)
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    app.setStyleSheet(stylesheet.build(DARK))
