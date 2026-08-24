"""Unit tests for the mute-timeframe duration parser."""

from __future__ import annotations

import pytest

from git_repo_status_check.duration import parse_duration

_DAY = 86400.0
_WEEK = 604800.0
_MONTH = 2592000.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1d", _DAY),
        ("1w", _WEEK),
        ("1m", _MONTH),
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
