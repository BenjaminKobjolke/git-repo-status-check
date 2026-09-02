"""Shared helpers for the integration tests: real temp git repos on disk.

Lives here rather than in each test module so the deterministic git identity below is
defined once -- the tests must not depend on the developer's global git config.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# Deterministic identity + no dependence on the developer's global git config.
# ``protocol.file.allow`` is needed for submodules and clones from a local path.
_GIT_ENV_ARGS = (
    "-c",
    "user.email=test@example.com",
    "-c",
    "user.name=Test",
    "-c",
    "protocol.file.allow=always",
    "-c",
    "commit.gpgsign=false",
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(repo), *_GIT_ENV_ARGS, *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    (path / "readme.txt").write_text("hello", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "init")
    return path
