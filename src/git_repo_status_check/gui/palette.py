"""Design tokens: every colour, spacing step and radius the window uses, defined once.

No hex literal or pixel size lives anywhere else in ``gui/`` (pinned by a test). The theme
is dark-only; a light palette would be a second ``Palette`` instance, nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """The neutral ramp, one accent, and the semantic colours that do not follow it."""

    window: str
    surface: str
    control: str
    control_hover: str
    control_pressed: str
    border: str
    text: str
    text_muted: str
    accent: str
    accent_text: str  # text drawn on an accent-filled control
    error: str  # semantic: a failed validation. Not the accent; stays red if the accent changes.


DARK = Palette(
    window="#181818",
    surface="#222222",
    control="#2B2B2B",
    control_hover="#343434",
    control_pressed="#3A3A3A",
    border="#383838",
    text="#F5F5F5",
    text_muted="#A8A8A8",  # 6.8:1 on the window background; muted, still readable
    accent="#20C55A",
    accent_text="#0B1F12",
    error="#F26D6D",
)

# Spacing scale in pixels: whitespace before borders before boxes.
SPACE_XS = 4
SPACE_S = 8
SPACE_M = 12
SPACE_L = 16
SPACE_XL = 24

RADIUS = 8

# Type scale in pixels.
FONT_HEADING = 22
FONT_BODY = 13
FONT_SMALL = 12
