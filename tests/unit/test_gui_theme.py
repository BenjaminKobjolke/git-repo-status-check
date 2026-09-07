"""Unit tests for the theme tokens and stylesheet -- the rules a restyle must not break."""

from __future__ import annotations

import re
from pathlib import Path

from git_repo_status_check.gui import palette, stylesheet
from git_repo_status_check.gui.window_chrome import colorref

_GUI_DIR = Path(palette.__file__).parent
_HEX_LITERAL = re.compile(r"#[0-9A-Fa-f]{6}\b")


def test_stylesheet_never_sets_a_minimum_size() -> None:
    sheet = stylesheet.build(palette.DARK)
    assert "min-width" not in sheet
    assert "min-height" not in sheet


def test_every_focusable_control_has_a_focus_style() -> None:
    sheet = stylesheet.build(palette.DARK)
    for selector in stylesheet.FOCUSABLE:
        assert f"{selector}:focus" in sheet, selector


def test_no_colour_literal_outside_the_palette() -> None:
    """Tokens, not values: a hex colour anywhere else in gui/ is a second home for it."""
    offenders = [
        path.name
        for path in _GUI_DIR.glob("*.py")
        if path.name != "palette.py" and _HEX_LITERAL.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_colorref_reverses_the_byte_order() -> None:
    assert colorref("#112233") == 0x332211
    assert colorref(palette.DARK.window) == colorref(palette.DARK.window.upper())
