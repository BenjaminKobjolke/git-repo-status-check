"""SQLite-backed store of per-repo ``--commit-ask`` state (via SQLAlchemy ORM).

A repo is identified by ``str(RepoStatus.path)``. Two independent tables hang off that key:
a mute row records the epoch second until which the repo should be silently skipped, and a
visit row records when its menu was last shown (so a re-run does not ask again straight
away). Time is passed in by callers so this module stays deterministic and easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Float, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Mute(Base):
    """One muted repo and its expiry (epoch seconds)."""

    __tablename__ = "mutes"

    repo_path: Mapped[str] = mapped_column(String, primary_key=True)
    muted_until: Mapped[float] = mapped_column(Float, nullable=False)


class Visit(Base):
    """The last time ``--commit-ask`` showed this repo's menu (epoch seconds)."""

    __tablename__ = "visits"

    repo_path: Mapped[str] = mapped_column(String, primary_key=True)
    visited_at: Mapped[float] = mapped_column(Float, nullable=False)


@dataclass(frozen=True)
class MuteRecord:
    """Typed view of a mute crossing the module boundary (no ORM/dict leaks out)."""

    path: str
    muted_until: float


class MuteStore:
    """Persist and query per-repo mutes and menu visits in a SQLite file.

    One engine covers both tables, so ``create_all`` adds ``visits`` to a database written
    by an older version on next open -- no migration step.
    """

    def __init__(self, db_path: Path) -> None:
        self._engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self._engine)

    def mute(self, repo_path: str, muted_until: float) -> None:
        """Mute ``repo_path`` until ``muted_until``; overwrites any existing mute."""
        with Session(self._engine) as session:
            session.merge(Mute(repo_path=repo_path, muted_until=muted_until))
            session.commit()

    def muted_until(self, repo_path: str, now: float) -> float | None:
        """Expiry of ``repo_path``'s mute if it is still active at ``now``, else ``None``."""
        with Session(self._engine) as session:
            row = session.get(Mute, repo_path)
            if row is None or row.muted_until <= now:
                return None
            return row.muted_until

    def list_active(self, now: float) -> list[MuteRecord]:
        """Active mutes at ``now``, soonest expiry first."""
        with Session(self._engine) as session:
            rows = session.scalars(
                select(Mute).where(Mute.muted_until > now).order_by(Mute.muted_until)
            )
            return [MuteRecord(path=r.repo_path, muted_until=r.muted_until) for r in rows]

    def record_visit(self, repo_path: str, visited_at: float) -> None:
        """Record that ``repo_path``'s menu was shown at ``visited_at``; overwrites."""
        with Session(self._engine) as session:
            session.merge(Visit(repo_path=repo_path, visited_at=visited_at))
            session.commit()

    def last_visit(self, repo_path: str) -> float | None:
        """When ``repo_path``'s menu was last shown, or ``None`` if it never was.

        Returned unfiltered by age: the caller owns the window (``min_visit_age``), so an
        old row simply stops mattering rather than needing to be pruned.
        """
        with Session(self._engine) as session:
            row = session.get(Visit, repo_path)
            return None if row is None else row.visited_at
