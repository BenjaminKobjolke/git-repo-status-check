"""Unit tests for the SQLAlchemy-backed mute store."""

from __future__ import annotations

from pathlib import Path

from git_repo_status_check.mute_store import MuteStore, PullMute, ScanSkip, muted_label

_REPO_PATH = Path("D:/GIT/foo")
_REPO = str(_REPO_PATH)


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


def test_pull_mutes_are_invisible_to_commit_mutes(tmp_path: Path) -> None:
    """The whole point of the second table: the two ask-modes must not silence each other."""
    db = tmp_path / "mutes.db"
    commit_store = MuteStore(db)
    pull_store = MuteStore(db, PullMute)

    pull_store.mute("D:/GIT/foo", muted_until=999.0)
    assert commit_store.muted_until("D:/GIT/foo", now=0.0) is None
    assert commit_store.list_active(now=0.0) == []

    commit_store.mute("D:/GIT/bar", muted_until=999.0)
    assert pull_store.muted_until("D:/GIT/bar", now=0.0) is None
    assert [r.path for r in pull_store.list_active(now=0.0)] == ["D:/GIT/foo"]


def test_muted_label_reports_the_remaining_time(store: MuteStore) -> None:
    store.mute("D:/GIT/foo", muted_until=100.0 + 2 * 86400)
    assert muted_label(store, "D:/GIT/foo", now=100.0) == "muted for 2 days"
    assert muted_label(store, "D:/GIT/unmuted", now=100.0) is None


def _scan_skip(store: MuteStore, min_visit_age: float | None = 3600.0) -> ScanSkip:
    return ScanSkip(store, min_visit_age, now=10_000.0, work="scanning")


def test_scan_skip_names_a_muted_repo(store: MuteStore) -> None:
    store.mute(_REPO, muted_until=10_000.0 + 2 * 86400.0)
    assert _scan_skip(store)(_REPO_PATH) == "muted for 2 days"


def test_scan_skip_names_a_recently_visited_repo(store: MuteStore) -> None:
    store.record_visit(_REPO, visited_at=10_000.0 - 600.0)
    assert _scan_skip(store)(_REPO_PATH) == "seen 10 minutes ago"


def test_scan_skip_mute_wins_over_a_fresh_visit(store: MuteStore) -> None:
    """An explicit mute is the user's own decision, so its label takes precedence."""
    store.mute(_REPO, muted_until=10_000.0 + 2 * 86400.0)
    store.record_visit(_REPO, visited_at=10_000.0)
    assert _scan_skip(store)(_REPO_PATH) == "muted for 2 days"


def test_scan_skip_passes_a_visit_older_than_the_window(store: MuteStore) -> None:
    store.record_visit(_REPO, visited_at=10_000.0 - 7200.0)
    assert _scan_skip(store)(_REPO_PATH) is None


def test_scan_skip_ignores_visits_when_min_visit_age_is_off(store: MuteStore) -> None:
    store.record_visit(_REPO, visited_at=10_000.0)
    assert _scan_skip(store, min_visit_age=None)(_REPO_PATH) is None


def test_scan_skip_counts_only_the_repos_it_held_back(store: MuteStore) -> None:
    store.record_visit(_REPO, visited_at=10_000.0)
    skip = _scan_skip(store)
    skip(_REPO_PATH)
    skip(Path("D:/GIT/never-seen"))
    assert skip.count == 1
    assert skip.summary() == (
        "\nSkipped 1 repo(s) without scanning (muted, or seen within min_visit_age). "
        "Pass --all to check them anyway."
    )


def test_scan_skip_summary_is_none_when_nothing_was_held_back(store: MuteStore) -> None:
    assert _scan_skip(store).summary() is None
