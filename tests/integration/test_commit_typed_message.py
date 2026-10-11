"""Typed commits are pushed to the configured remote."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from git_repo_status_check import committer, menu
from git_repo_status_check.models import RepoStatus
from git_repo_status_check.mute_store import MuteStore

from .helpers import _git, _init_repo


@pytest.mark.parametrize("has_upstream", [True, False])
def test_typed_message_commits_and_pushes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, has_upstream: bool
) -> None:
    repo = _init_repo(tmp_path / "work repo")
    remote = tmp_path / "bare remote.git"
    subprocess.run(("git", "init", "--bare", str(remote)), check=True, capture_output=True)
    _git(repo, "remote", "add", "origin", str(remote))
    if has_upstream:
        _git(repo, "push", "-u", "origin", "main")
    for key, value in (
        ("user.email", "test@example.com"),
        ("user.name", "Test"),
        ("commit.gpgsign", "false"),
    ):
        _git(repo, "config", key, value)
    (repo / "untracked.txt").write_text("new", encoding="utf-8")
    (repo / "readme.txt").write_text("edited", encoding="utf-8")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(menu, "choose", lambda _items, _title: "t")
    monkeypatch.setattr(menu, "ask_text", lambda _prompt: "typed message")
    monkeypatch.setattr(menu, "pause", lambda: None)

    assert committer.commit_interactive(
        [RepoStatus(path=repo, dirty_count=2)], None, MuteStore(tmp_path / "mutes.db")
    )

    assert _git(repo, "status", "--porcelain") == ""
    assert _git(repo, "log", "-1", "--format=%s") == "typed message"
    remote_head = _git(repo, "--git-dir", str(remote), "rev-parse", "main")
    assert remote_head == _git(repo, "rev-parse", "HEAD")
    if not has_upstream:
        assert _git(repo, "rev-parse", "--abbrev-ref", "@{u}") == "origin/main"
