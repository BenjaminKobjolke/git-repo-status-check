"""Label factories: the object-name + word-wrap pairing, written once for every page."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from . import stylesheet


def _label(text: str, object_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setWordWrap(True)  # an unwrapped sentence would set the window's width floor
    return label


def heading(text: str) -> QLabel:
    return _label(text, stylesheet.HEADING)


def subheading(text: str) -> QLabel:
    return _label(text, stylesheet.SUBHEADING)


def hint(text: str) -> QLabel:
    return _label(text, stylesheet.HINT)


def menu_title(text: str) -> QLabel:
    return _label(text, stylesheet.MENU_TITLE)
