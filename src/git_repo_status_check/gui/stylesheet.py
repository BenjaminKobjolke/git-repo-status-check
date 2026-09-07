"""The one application stylesheet, built from the palette tokens.

Object names are constants here, never string literals at call sites -- a typo'd literal
fails silently (the widget just stays unstyled). Two rules survive every edit: no
``min-width``/``min-height`` anywhere (the window must shrink to anything; pages scroll),
and an explicit ``:focus`` border on every focusable control, since Fusion's own focus ring
disappears the moment a control gets a custom background. Both are pinned by tests.
"""

from __future__ import annotations

from . import palette
from .palette import Palette

HEADING = "Heading"
SUBHEADING = "Subheading"
HINT = "Hint"
PRIMARY = "Primary"
LOG = "Log"
MENU_TITLE = "MenuTitle"
MESSAGE_ERROR = "MessageError"

# Every control a user can tab to; each gets a ``:focus`` rule below (pinned by a test).
FOCUSABLE: tuple[str, ...] = (
    "QPushButton",
    "QLineEdit",
    "QListWidget",
    "QPlainTextEdit",
    "QSpinBox",
    "QCheckBox",
    "QTabBar::tab",
)


def build(tokens: Palette) -> str:
    """The QSS for ``tokens``; applied once to the ``QApplication``."""
    return f"""
QWidget {{
    background-color: {tokens.window};
    color: {tokens.text};
    font-size: {palette.FONT_BODY}px;
}}
QLabel {{ background-color: transparent; }}
QLabel#{HEADING} {{ font-size: {palette.FONT_HEADING}px; font-weight: 600; }}
QLabel#{SUBHEADING} {{ color: {tokens.text_muted}; }}
QLabel#{HINT} {{ color: {tokens.text_muted}; font-size: {palette.FONT_SMALL}px; }}
QLabel#{MENU_TITLE} {{ font-weight: 600; }}
QLabel#{MESSAGE_ERROR} {{ color: {tokens.error}; }}

QScrollArea {{ border: none; }}
QStatusBar {{ color: {tokens.text_muted}; border-top: 1px solid {tokens.border}; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background-color: transparent;
    color: {tokens.text_muted};
    padding: {palette.SPACE_S}px {palette.SPACE_L}px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {tokens.accent}; border-bottom: 2px solid {tokens.accent}; }}
QTabBar::tab:focus {{ border-bottom: 2px solid {tokens.text}; }}

QPushButton {{
    background-color: {tokens.control};
    color: {tokens.text};
    border: 1px solid {tokens.border};
    border-radius: {palette.RADIUS}px;
    padding: {palette.SPACE_S}px {palette.SPACE_M}px;
}}
QPushButton:hover {{ background-color: {tokens.control_hover}; }}
QPushButton:pressed {{ background-color: {tokens.control_pressed}; }}
QPushButton:focus {{ border: 1px solid {tokens.accent}; }}
QPushButton:disabled {{ color: {tokens.text_muted}; }}
QPushButton#{PRIMARY} {{
    background-color: {tokens.accent};
    color: {tokens.accent_text};
    border-color: {tokens.accent};
    font-weight: 600;
}}
QPushButton#{PRIMARY}:focus {{ border: 1px solid {tokens.text}; }}
QPushButton#{PRIMARY}:disabled {{ background-color: {tokens.control}; color: {tokens.text_muted}; }}

QLineEdit, QSpinBox, QListWidget, QPlainTextEdit {{
    background-color: {tokens.surface};
    border: 1px solid {tokens.border};
    border-radius: {palette.RADIUS}px;
    padding: {palette.SPACE_XS}px {palette.SPACE_S}px;
    selection-background-color: {tokens.accent};
    selection-color: {tokens.accent_text};
}}
QLineEdit:focus, QSpinBox:focus, QListWidget:focus, QPlainTextEdit:focus {{
    border: 1px solid {tokens.accent};
}}
QPlainTextEdit#{LOG} {{ font-family: Consolas, "Courier New", monospace; }}
QListWidget::item {{ padding: {palette.SPACE_XS}px; }}
QListWidget::item:selected {{ background-color: {tokens.accent}; color: {tokens.accent_text}; }}

QCheckBox {{ spacing: {palette.SPACE_S}px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {tokens.border};
    border-radius: {palette.SPACE_XS}px;
    background-color: {tokens.surface};
}}
QCheckBox::indicator:checked {{ background-color: {tokens.accent}; border-color: {tokens.accent}; }}
QCheckBox:focus {{ color: {tokens.accent}; }}

QScrollBar:vertical {{ background: {tokens.window}; width: {palette.SPACE_M}px; }}
QScrollBar::handle:vertical {{
    background: {tokens.control_hover};
    border-radius: {palette.SPACE_XS}px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""
