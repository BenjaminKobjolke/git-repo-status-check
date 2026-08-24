"""SQLite-backed store of muted repos (via SQLAlchemy ORM).

A repo is identified by ``str(RepoStatus.path)``. A mute row records the epoch second
until which the repo should be silently skipped in ``--commit-ask``. Time is passed in by
callers so this module stays deterministic and easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Float, String, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Mute(Base):
    """One muted repo and its expiry (epoch seconds)."""

    __tablename__ = "mutes"

    repo_path: Mapped[str] = mapped_column(String, primary_key=True)
    muted_until: Mapped[float] = mapped_column(Float, nullable=False)


@dataclass(frozen=True)
class MuteRecord:
    """Typed view of a mute crossing the module boundary (no ORM/dict leaks out)."""

    path: str
    muted_until: float


class MuteStore:
    """Persist and query repo mutes in a SQLite file."""

    def __init__(self, db_path: Path) -> None:
        self._engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self._engine)

    def mute(self, repo_path: str, muted_until: float) -> None:
        """Mute ``repo_path`` until ``muted_until``; overwrites any existing mute."""
        with Session(self._engine) as session:
            session.merge(Mute(repo_path=repo_path, muted_until=muted_until))
            session.commit()

    def is_muted(self, repo_path: str, now: float) -> bool:
        """True if ``repo_path`` has a mute that is still active at ``now``."""
        with Session(self._engine) as session:
            row = session.get(Mute, repo_path)
            return row is not None and row.muted_until > now

    def list_active(self, now: float) -> list[MuteRecord]:
        """Active mutes at ``now``, soonest expiry first."""
        with Session(self._engine) as session:
            rows = session.scalars(
                select(Mute).where(Mute.muted_until > now).order_by(Mute.muted_until)
            )
            return [MuteRecord(path=r.repo_path, muted_until=r.muted_until) for r in rows]

    def purge_expired(self, now: float) -> None:
        """Delete mutes whose expiry is at or before ``now``."""
        with Session(self._engine) as session:
            session.execute(delete(Mute).where(Mute.muted_until <= now))
            session.commit()
