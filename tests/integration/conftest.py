"""Shared integration fixtures: one offscreen QApplication for the whole session."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# Set before Qt is imported anywhere: offscreen rendering needs no display and no focus.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qt_app() -> Iterator[object]:
    from PySide6.QtWidgets import QApplication

    from git_repo_status_check.gui import i18n, theme

    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    theme.apply_dark(app)
    i18n.configure(language=i18n.FALLBACK_LANGUAGE)  # not the developer's OS language
    yield app
