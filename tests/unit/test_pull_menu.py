"""Unit tests for the --pull-ask menu itself: which entries it offers, and what each runs.

The walk and the visit bookkeeping are in ``test_pull_interactive``; git calls are stubbed
throughout, so nothing here touches a real repo or the network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo_status_check import puller
from git_repo_status_check.constants import PULL_MENU, PULL_MORE_MENU
from git_repo_status_check.mute_store import MuteStore

from .helpers import _behind, _run_pull


def test_stash_entry_is_hidden_on_a_clean_repo() -> None:
    """Nothing to stash there -- offering it would only produce a failure line."""
    assert puller.pull_menu(0) == PULL_MENU


def test_stash_entry_follows_pull_on_a_dirty_repo() -> None:
    labels = [label for label, _ in puller.pull_menu(3)]
    assert labels == [
        "Pull",
        "Stash changes and pull",
        "More actions...",
        "Skip",
        "Mute repo",
        "Abort",
    ]


def test_more_submenu_offers_explorer_rename_stash_and_back() -> None:
    labels = [label for label, _ in PULL_MORE_MENU]
    assert labels == ["Open in file explorer", "Rename repo", "Stash changes", "Back"]


def test_explorer_choice_opens_the_repo_and_stays_in_the_submenu(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    opened: list[tuple[Path, str | None]] = []

    def _explorer(path: Path, command: str | None) -> None:
        opened.append((path, command))

    monkeypatch.setattr(puller, "run_explorer", _explorer)
    # more -> explorer -> back -> skip
    pulled = _run_pull(monkeypatch, pull_store, [_behind("repo0")], "more", "e", "b", "s")
    assert opened == [(Path("repo0"), None)]
    assert pulled == []


def test_rename_choice_renames_and_moves_on(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    """A renamed repo is gone from this path, so nothing is pulled and the walk goes on."""
    renamed: list[tuple[Path, str | None]] = []

    def _rename(path: Path, prefix: str | None) -> bool:
        renamed.append((path, prefix))
        return True

    monkeypatch.setattr(puller, "run_rename", _rename)
    repos = [_behind("repo0"), _behind("repo1")]
    pulled = _run_pull(monkeypatch, pull_store, repos, "more", "r", "s")
    assert renamed == [(Path("repo0"), None)]
    assert pulled == []


def test_a_failed_rename_re_asks(monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore) -> None:
    monkeypatch.setattr(puller, "run_rename", lambda _path, _prefix: False)
    pulled = _run_pull(monkeypatch, pull_store, [_behind("repo0")], "more", "r", "b", "p")
    assert pulled == [Path("repo0")]


def _run_stashing(
    monkeypatch: pytest.MonkeyPatch,
    store: MuteStore,
    *choices: str,
    stash_ok: bool = True,
) -> tuple[list[Path], list[Path]]:
    """Drive one dirty behind-repo through the menu; return (stashed, pulled) paths."""
    stashed: list[Path] = []

    def run_stash(path: Path) -> bool:
        stashed.append(path)
        return stash_ok

    monkeypatch.setattr(puller, "run_stash", run_stash)
    pulled = _run_pull(monkeypatch, store, [_behind("repo0", dirty_count=2)], *choices)
    return stashed, pulled


def test_stash_choice_stashes_then_pulls(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    stashed, pulled = _run_stashing(monkeypatch, pull_store, "t")
    assert stashed == [Path("repo0")]
    assert pulled == [Path("repo0")]


def test_a_failed_stash_does_not_pull(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    """The dirty tree is exactly what the pull would trip over, so do not pull into it.

    The menu comes back after the failed stash; Skip is what leaves the repo alone.
    """
    stashed, pulled = _run_stashing(monkeypatch, pull_store, "t", "s", stash_ok=False)
    assert stashed == [Path("repo0")]
    assert pulled == []


def test_submenu_stash_returns_to_the_menu_without_pulling(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    """A plain stash puts the changes aside; pulling stays a separate decision."""
    stashed, pulled = _run_stashing(monkeypatch, pull_store, "more", "s", "p")
    assert stashed == [Path("repo0")]
    assert pulled == [Path("repo0")]


def test_a_failed_submenu_stash_stays_in_the_submenu(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    stashed, pulled = _run_stashing(monkeypatch, pull_store, "more", "s", "b", "s", stash_ok=False)
    assert stashed == [Path("repo0")]
    assert pulled == []


def test_plain_pull_never_stashes(monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore) -> None:
    stashed, pulled = _run_stashing(monkeypatch, pull_store, "p")
    assert stashed == []
    assert pulled == [Path("repo0")]


def test_failed_pull_re_asks_the_same_repo(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    """A failed pull brings the menu back, so stash-then-pull is still reachable."""
    pulled = _run_pull(
        monkeypatch,
        pull_store,
        [_behind("repo0", dirty_count=2)],
        "p",
        "p",
        fail_pulls=1,
    )
    assert pulled == [Path("repo0"), Path("repo0")]


def test_failed_pull_then_skip_moves_on(
    monkeypatch: pytest.MonkeyPatch, pull_store: MuteStore
) -> None:
    repos = [_behind("repo0"), _behind("repo1")]
    pulled = _run_pull(monkeypatch, pull_store, repos, "p", "s", "s", fail_pulls=1)
    assert pulled == [Path("repo0")]
