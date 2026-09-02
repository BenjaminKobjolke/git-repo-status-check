"""SQLite-backed store of per-repo ask-mode state (via SQLAlchemy ORM).

A repo is identified by ``str(RepoStatus.path)``. Tables hang off that key: a mute row
records the epoch second until which the repo should be silently skipped, and a visit row
records when its menu was last shown (so a re-run does not ask again straight away). Time is passed in by callers so this module stays deterministic and easy
to test.

Each ask-mode gets its own mute and visit tables rather than one table with a "kind"
column: a column cannot be added to an existing ``mutes.db`` by ``create_all``, whereas a
new table simply appears on next open. The mode picks its tables by passing the models to
``MuteStore``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Float, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .constants import SKIP_LABEL_MUTED, SKIP_LABEL_VISITED
from .duration import format_duration


class Base(DeclarativeBase):
    pass


class MuteRow(Base):
    """Shared shape of a mute row: a repo key and its expiry (epoch seconds).

    ``__abstract__`` means no table of its own — each ask-mode's model inherits the two
    columns and adds only its table name, so the shape is written once.
    """

    __abstract__ = True

    repo_path: Mapped[str] = mapped_column(String, primary_key=True)
    muted_until: Mapped[float] = mapped_column(Float, nullable=False)


class Mute(MuteRow):
    """One repo muted for ``--commit-ask``."""

    __tablename__ = "mutes"


class PullMute(MuteRow):
    """One repo muted for ``--pull-ask`` — its own table, so it cannot silence commits."""

    __tablename__ = "pull_mutes"


class VisitRow(Base):
    """Shared shape of a visit row: a repo key and when its menu was last shown."""

    __abstract__ = True

    repo_path: Mapped[str] = mapped_column(String, primary_key=True)
    visited_at: Mapped[float] = mapped_column(Float, nullable=False)


class Visit(VisitRow):
    """The last time ``--commit-ask`` showed this repo's menu (epoch seconds)."""

    __tablename__ = "visits"


class PullVisit(VisitRow):
    """The last time ``--pull-ask`` showed this repo's menu; its own table, like the mutes."""

    __tablename__ = "pull_visits"


@dataclass(frozen=True)
class MuteRecord:
    """Typed view of a mute crossing the module boundary (no ORM/dict leaks out)."""

    path: str
    muted_until: float


class MuteStore:
    """Persist and query per-repo mutes and menu visits in a SQLite file.

    One engine covers every table, so ``create_all`` adds a missing one to a database
    written by an older version on next open -- no migration step. ``mute_model`` and
    ``visit_model`` select which pair of tables this store reads and writes, which is what
    keeps the two ask-modes from silencing each other.
    """

    def __init__(
        self,
        db_path: Path,
        mute_model: type[MuteRow] = Mute,
        visit_model: type[VisitRow] = Visit,
    ) -> None:
        self._engine = create_engine(f"sqlite:///{db_path}")
        self._mute_model = mute_model
        self._visit_model = visit_model
        Base.metadata.create_all(self._engine)

    def mute(self, repo_path: str, muted_until: float) -> None:
        """Mute ``repo_path`` until ``muted_until``; overwrites any existing mute."""
        with Session(self._engine) as session:
            session.merge(self._mute_model(repo_path=repo_path, muted_until=muted_until))
            session.commit()

    def muted_until(self, repo_path: str, now: float) -> float | None:
        """Expiry of ``repo_path``'s mute if it is still active at ``now``, else ``None``."""
        with Session(self._engine) as session:
            row = session.get(self._mute_model, repo_path)
            if row is None or row.muted_until <= now:
                return None
            return row.muted_until

    def list_active(self, now: float) -> list[MuteRecord]:
        """Active mutes at ``now``, soonest expiry first."""
        with Session(self._engine) as session:
            model = self._mute_model
            rows = session.scalars(
                select(model).where(model.muted_until > now).order_by(model.muted_until)
            )
            return [MuteRecord(path=r.repo_path, muted_until=r.muted_until) for r in rows]

    def record_visit(self, repo_path: str, visited_at: float) -> None:
        """Record that ``repo_path``'s menu was shown at ``visited_at``; overwrites."""
        with Session(self._engine) as session:
            session.merge(self._visit_model(repo_path=repo_path, visited_at=visited_at))
            session.commit()

    def last_visit(self, repo_path: str) -> float | None:
        """When ``repo_path``'s menu was last shown, or ``None`` if it never was.

        Returned unfiltered by age: the caller owns the window (``min_visit_age``), so an
        old row simply stops mattering rather than needing to be pruned.
        """
        with Session(self._engine) as session:
            row = session.get(self._visit_model, repo_path)
            return None if row is None else row.visited_at


def muted_label(store: MuteStore, repo_path: str, now: float) -> str | None:
    """The ``muted for 2 days`` label for ``repo_path``, or None when it is not muted.

    Shared by both ask-modes so the wording and the remaining-time arithmetic are written
    once (``--commit-ask`` reaches it through ``main.build_skip_reason``).
    """
    expiry = store.muted_until(repo_path, now)
    if expiry is None:
        return None
    return SKIP_LABEL_MUTED.format(duration=format_duration(expiry - now))


def skip_reason(
    store: MuteStore, repo_path: str, now: float, min_visit_age: float | None
) -> str | None:
    """Why an ask-mode will leave ``repo_path`` alone this run, or None to act on it.

    The two reasons both modes share, most-deliberate first: an explicit mute, then a menu
    you already saw. ``--commit-ask`` layers its own "changed too recently" test on top of
    this (see ``main.build_skip_reason``); ``--pull-ask`` has nothing to add.
    """
    muted = muted_label(store, repo_path, now)
    if muted is not None:
        return muted
    if min_visit_age is None:
        return None
    visited_at = store.last_visit(repo_path)
    if visited_at is None:
        return None
    since_visit = now - visited_at
    if since_visit >= min_visit_age:
        return None
    return SKIP_LABEL_VISITED.format(duration=format_duration(since_visit))
