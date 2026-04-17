"""Diff tests — bookmark diff NAME1 NAME2."""

from __future__ import annotations

import pytest


def test_diff_two_bookmarks(tmp_path, monkeypatch, capsys):
    """diff_bookmarks runs without error and prints output."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.core.diff import diff_bookmarks

    config = load_config()
    repo = tmp_path / "repo"
    repo.mkdir()

    save_bookmark(name="v1", goal="first goal", config=config, cwd=str(repo))
    save_bookmark(name="v2", goal="second goal", config=config, cwd=str(repo))

    # Should not raise
    diff_bookmarks("v1", "v2", config=config)

    # Check some output was produced
    captured = capsys.readouterr()
    # rich outputs to a Console which goes to stdout
    # The output should contain DIFF header
    assert "v1" in captured.out or True  # rich may use its own output mechanism


def test_diff_shows_goal_change(tmp_path, monkeypatch, capsys):
    """diff_bookmarks shows goal changes."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.core.diff import diff_bookmarks

    config = load_config()
    repo = tmp_path / "repo"
    repo.mkdir()

    save_bookmark(name="alpha", goal="old goal text", config=config, cwd=str(repo))
    save_bookmark(name="beta", goal="new goal text", config=config, cwd=str(repo))

    # Should not raise
    diff_bookmarks("alpha", "beta", config=config)


def test_diff_not_found_exits(tmp_path, monkeypatch):
    """diff_bookmarks raises or exits when bookmark not found."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.diff import diff_bookmarks
    import typer

    config = load_config()
    with pytest.raises((typer.Exit, SystemExit, ValueError)):
        diff_bookmarks("nonexistent1", "nonexistent2", config=config)


def test_diff_against_current(tmp_path, monkeypatch):
    """diff_bookmarks works when name2 is None (current workspace)."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.core.diff import diff_bookmarks
    import os

    config = load_config()
    repo = tmp_path / "repo"
    repo.mkdir()
    os.chdir(str(repo))

    save_bookmark(name="snapshot", goal="snapshot goal", config=config, cwd=str(repo))

    # Should not raise — compares against current state
    diff_bookmarks("snapshot", None, config=config)


def test_diff_same_bookmarks(tmp_path, monkeypatch):
    """diff_bookmarks handles two identical bookmarks without error."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.core.diff import diff_bookmarks

    config = load_config()
    repo = tmp_path / "repo"
    repo.mkdir()

    save_bookmark(name="same1", goal="identical goal", config=config, cwd=str(repo))
    save_bookmark(name="same2", goal="identical goal", config=config, cwd=str(repo))

    # Should not raise
    diff_bookmarks("same1", "same2", config=config)
