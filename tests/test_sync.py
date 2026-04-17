"""Sync tests — §3 Flow C of design doc."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _init_git_user(repo_path: Path) -> None:
    """Configure git user in repo for commits."""
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo_path), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo_path), check=True, capture_output=True,
    )


def test_sync_init_creates_git_repo(tmp_path, monkeypatch):
    """sync_init creates a git repo in the sync dir."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.sync import sync_init

    # Use a local bare repo as remote (no network needed)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)

    config = load_config()
    sync_dir = tmp_path / "sync"
    sync_init(str(remote), sync_dir=sync_dir, config=config)

    assert (sync_dir / ".git").exists()
    assert (sync_dir / "bookmarks.db").exists()


def test_sync_init_creates_git_repo_with_remote(tmp_path, monkeypatch):
    """sync_init sets the git remote correctly."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.sync import sync_init

    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)

    config = load_config()
    sync_dir = tmp_path / "sync"
    sync_init(str(remote), sync_dir=sync_dir, config=config)

    result = subprocess.run(
        ["git", "-C", str(sync_dir), "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert str(remote) in result.stdout


def test_sync_push_pull_roundtrip(tmp_path, monkeypatch):
    """Bookmark saved on 'machine A' appears after pull on 'machine B'."""
    home_a = tmp_path / "home_a"
    home_a.mkdir()
    monkeypatch.setenv("BOOKMARK_HOME", str(home_a))

    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.sync import sync_clone, sync_init, sync_pull, sync_push
    from bookmark.storage.db import list_bookmarks, open_db

    # Set up remote
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)

    # Machine A: save a bookmark and push
    config_a = load_config()
    repo_a = tmp_path / "repo_a"
    repo_a.mkdir()
    save_bookmark(name="sync-test", goal="testing sync", config=config_a, cwd=str(repo_a))

    sync_dir_a = tmp_path / "sync_a"
    sync_init(str(remote), sync_dir=sync_dir_a, config=config_a)
    _init_git_user(sync_dir_a)
    sync_push(sync_dir=sync_dir_a, config=config_a)

    # Machine B: clone and verify
    home_b = tmp_path / "home_b"
    home_b.mkdir()
    monkeypatch.setenv("BOOKMARK_HOME", str(home_b))
    config_b = load_config()

    sync_dir_b = tmp_path / "sync_b"
    sync_clone(str(remote), sync_dir=sync_dir_b, config=config_b)

    conn_b = open_db(home_b / "bookmarks.db")
    bms = list_bookmarks(conn_b, include_auto=True)
    conn_b.close()
    assert any(bm.name == "sync-test" for bm in bms)


def test_sync_clone_copies_db(tmp_path, monkeypatch):
    """sync_clone copies bookmarks.db to bookmark home."""
    home_a = tmp_path / "home_a"
    home_a.mkdir()
    monkeypatch.setenv("BOOKMARK_HOME", str(home_a))

    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.sync import sync_clone, sync_init, sync_push

    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)

    config_a = load_config()
    repo_a = tmp_path / "repo_a"
    repo_a.mkdir()
    save_bookmark(name="clone-test", goal="testing clone", config=config_a, cwd=str(repo_a))

    sync_dir_a = tmp_path / "sync_a"
    sync_init(str(remote), sync_dir=sync_dir_a, config=config_a)
    _init_git_user(sync_dir_a)
    sync_push(sync_dir=sync_dir_a, config=config_a)

    # Clone into machine B
    home_b = tmp_path / "home_b"
    home_b.mkdir()
    monkeypatch.setenv("BOOKMARK_HOME", str(home_b))
    config_b = load_config()

    sync_dir_b = tmp_path / "sync_b"
    sync_clone(str(remote), sync_dir=sync_dir_b, config=config_b)

    assert (home_b / "bookmarks.db").exists()


def test_sync_push_raises_if_not_initialized(tmp_path, monkeypatch):
    """sync_push raises RuntimeError if sync dir is not a git repo."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.sync import sync_push

    config = load_config()
    sync_dir = tmp_path / "not_a_repo"
    sync_dir.mkdir()

    with pytest.raises(RuntimeError, match="not a git repo"):
        sync_push(sync_dir=sync_dir, config=config)
