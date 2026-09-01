"""Unit tests for the SQLAlchemy-backed mute store."""

from __future__ import annotations

from pathlib import Path

from git_repo_status_check.mute_store import MuteStore


def test_list_active_excludes_expired_and_sorts_by_expiry(store: MuteStore) -> None:
    store.mute("D:/GIT/b", muted_until=300.0)
    store.mute("D:/GIT/a", muted_until=200.0)
    store.mute("D:/GIT/old", muted_until=50.0)

    active = store.list_active(now=100.0)

    assert [r.path for r in active] == ["D:/GIT/a", "D:/GIT/b"]
    assert [r.muted_until for r in active] == [200.0, 300.0]


def test_mute_upserts_same_repo(store: MuteStore) -> None:
    store.mute("D:/GIT/foo", muted_until=100.0)
    store.mute("D:/GIT/foo", muted_until=500.0)

    active = store.list_active(now=0.0)
    assert len(active) == 1
    assert active[0].muted_until == 500.0


def test_persists_across_instances(tmp_path: Path) -> None:
    db = tmp_path / "mutes.db"
    MuteStore(db).mute("D:/GIT/foo", muted_until=999.0)
    assert MuteStore(db).muted_until("D:/GIT/foo", now=0.0) == 999.0


def test_muted_until_returns_expiry_only_while_active(store: MuteStore) -> None:
    store.mute("D:/GIT/foo", muted_until=100.0)
    assert store.muted_until("D:/GIT/foo", now=50.0) == 100.0
    assert store.muted_until("D:/GIT/foo", now=100.0) is None  # boundary: not strictly after
    assert store.muted_until("D:/GIT/unknown", now=0.0) is None


def test_last_visit_round_trips(store: MuteStore) -> None:
    store.record_visit("D:/GIT/foo", visited_at=1234.0)
    assert store.last_visit("D:/GIT/foo") == 1234.0


def test_last_visit_of_unvisited_repo_is_none(store: MuteStore) -> None:
    assert store.last_visit("D:/GIT/never-seen") is None


def test_record_visit_upserts_same_repo(store: MuteStore) -> None:
    store.record_visit("D:/GIT/foo", visited_at=100.0)
    store.record_visit("D:/GIT/foo", visited_at=500.0)
    assert store.last_visit("D:/GIT/foo") == 500.0


def test_visits_are_independent_of_mutes(store: MuteStore) -> None:
    """Separate tables: a visit must not show up as a mute, nor a mute as a visit."""
    store.record_visit("D:/GIT/foo", visited_at=100.0)
    assert store.list_active(now=0.0) == []
    store.mute("D:/GIT/bar", muted_until=999.0)
    assert store.last_visit("D:/GIT/bar") is None


def test_visits_persist_across_instances(tmp_path: Path) -> None:
    db = tmp_path / "mutes.db"
    MuteStore(db).record_visit("D:/GIT/foo", visited_at=42.0)
    assert MuteStore(db).last_visit("D:/GIT/foo") == 42.0
