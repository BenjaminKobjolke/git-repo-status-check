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
    """Every way out of the menu counts as "you looked at it" -- see main.build_skip_reason."""
    monkeypatch.setattr(committer.time, "time", lambda: 1000.0)
    _answers(monkeypatch, *answers)
    committer.commit_interactive(_statuses(1), "do-commit", store)

    assert store.last_visit(str(Path("repo0"))) == 1000.0, label


def test_abort_still_records_the_repo_you_were_shown(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    # The visit is written before the menu is drawn, so the repo you bailed out on does not
    # greet you again on the very next run.
    monkeypatch.setattr(committer.time, "time", lambda: 1000.0)
    _answers(monkeypatch, "a")
    committer.commit_interactive(_statuses(1), "do-commit", store)

    assert store.last_visit(str(Path("repo0"))) == 1000.0


def test_abort_leaves_the_repos_you_never_saw_unvisited(
    monkeypatch: pytest.MonkeyPatch, mock_run: MagicMock, store: MuteStore
) -> None:
    """Being shown a repo settles it; the ones the loop never reached stay untouched."""
    monkeypatch.setattr(committer.time, "time", lambda: 1000.0)
    _answers(monkeypatch, "s", "a")
    committer.commit_interactive(_statuses(3), "do-commit", store)

    assert store.last_visit(str(Path("repo0"))) == 1000.0  # skipped
    assert store.last_visit(str(Path("repo1"))) == 1000.0  # shown, then aborted
    assert store.last_visit(str(Path("repo2"))) is None  # never reached
