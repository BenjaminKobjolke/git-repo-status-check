"""Unit tests for the commit menu recording a visit per repo (see min_visit_age)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from git_repo_status_check import committer
from git_repo_status_check.mute_store import MuteStore

from .helpers import _answers, _statuses


@pytest.mark.parametrize(
    ("answers", "label"),
    [
        (("c",), "commit"),
        (("s",), "skip"),
        (("m", "m", "1w"), "mute"),
        (("m", "b", "s"), "submenu then skip"),
    ],
)
def test_leaving_a_repos_menu_records_a_visit(
    monkeypatch: pytest.MonkeyPatch,
    mock_run: MagicMock,
    store: MuteStore,
    answers: tuple[str, ...],
    label: str,
) -> None:
    """Every way out but Abort counts as "you looked at it" -- see main.build_skip_reason."""
    monkeypatch.setattr(committer.time, "time", lambda: 1000.0)
    _answers(monkeypatch, *answers)
    committer.commit_interactive(_statuses(1), "do-commit", store)

    assert store.last_visit(str(Path("repo0"))) == 1000.0, label


def test_abort_records_no_visit(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    # Bailing out is not a decision about this repo, so it must be prompted again next run.
    monkeypatch.setattr(committer.time, "time", lambda: 1000.0)
    _answers(monkeypatch, "a")
    committer.commit_interactive(_statuses(1), "do-commit", store)

    assert store.last_visit(str(Path("repo0"))) is None


def test_abort_leaves_later_repos_unvisited(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    monkeypatch.setattr(committer.time, "time", lambda: 1000.0)
    _answers(monkeypatch, "s", "a")
    committer.commit_interactive(_statuses(2), "do-commit", store)

    assert store.last_visit(str(Path("repo0"))) == 1000.0
    assert store.last_visit(str(Path("repo1"))) is None
