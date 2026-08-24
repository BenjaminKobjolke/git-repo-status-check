"""Parse mute timeframes like ``1d`` / ``1w`` / ``1m`` / ``3d`` into seconds."""

from __future__ import annotations

import re

from .constants import DURATION_UNIT_SECONDS

# <positive int><unit>, unit case-insensitive; no decimals, no sign.
_PATTERN = re.compile(r"^(\d+)([a-z])$", re.IGNORECASE)


def parse_duration(text: str) -> float | None:
    """Return the timeframe in seconds, or ``None`` if ``text`` is malformed.

    Accepts a positive integer followed by a unit (``d``/``w``/``m``), optionally
    surrounded by whitespace. Zero, decimals, negatives and unknown units are rejected.
    """
    match = _PATTERN.match(text.strip())
    if match is None:
        return None
    count = int(match.group(1))
    seconds = DURATION_UNIT_SECONDS.get(match.group(2).lower())
    if count <= 0 or seconds is None:
        return None
    return float(count * seconds)
