"""Unit tests for the mute-timeframe duration parser and formatter."""

from __future__ import annotations

import pytest

from git_repo_status_check.duration import format_duration, parse_duration

_HOUR = 3600.0
_DAY = 86400.0
_WEEK = 604800.0
_MONTH = 2592000.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1h", _HOUR),
        ("1d", _DAY),
        ("1w", _WEEK),
        ("1m", _MONTH),
        ("2h", 2 * _HOUR),
        ("3d", 3 * _DAY),
        ("2w", 2 * _WEEK),
        (" 1d ", _DAY),  # surrounding whitespace tolerated
        ("1D", _DAY),  # case-insensitive unit
    ],
)
def test_valid_durations(text: str, expected: float) -> None:
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "5", "1y", "d", "-1d", "0d", "1.5d", "w1", "abc"])
def test_invalid_durations_return_none(text: str) -> None:
    assert parse_duration(text) is None


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (30.0, "less than a minute"),
        (60.0, "1 minute"),
        (150.0, "2 minutes"),
        (_HOUR, "1 hour"),
        (5 * _HOUR, "5 hours"),
        (_DAY, "1 day"),
        (3 * _DAY, "3 days"),
        (_WEEK, "1 week"),
        (2 * _WEEK, "2 weeks"),
        (_MONTH, "1 month"),
        (2 * _MONTH, "2 months"),
        (-5.0, "less than a minute"),  # already expired -- never shows a negative
    ],
)
def test_format_duration(seconds: float, expected: str) -> None:
    assert format_duration(seconds) == expected
