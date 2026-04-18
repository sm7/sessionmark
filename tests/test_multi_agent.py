"""Unified-storage invariant — §11.1 of design doc.

Tests that multiple agent sources all share the same SQLite database
and that filtering by source works correctly.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from bookmark.config import Config
from bookmark.core.save import save_bookmark
from bookmark.core.resume import show_bookmark
from bookmark.storage.db import list_bookmarks, open_db


def _make_config(home: Path) -> Config:
    """Build a Config pointing at the given tmp home."""
    return Config(home=home, default_source="terminal", redact_enabled=True, blob_compress=False)


def test_multi_agent_unified_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Given three sessionmark saves with different --source values:
    1. sessionmark list returns exactly 3 rows with correct sources
    2. sessionmark list --source cursor returns exactly 1 row
    3. SQLite has exactly 1 bookmarks table with 3 rows
    4. sessionmark show <name> renders same structure for all 3
    """
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    config = _make_config(tmp_path)

    # Create a fake repo dir (no git needed for this test)
    repo = tmp_path / "repo"
    repo.mkdir()

    # ------------------------------------------------------------------
    # Save three bookmarks with different sources
    # ------------------------------------------------------------------
    bm_alpha = save_bookmark(
        name="alpha",
        goal="alpha goal",
        source="claude-code",
        config=config,
        cwd=str(repo),
    )
    bm_beta = save_bookmark(
        name="beta",
        goal="beta goal",
        source="cursor",
        config=config,
        cwd=str(repo),
    )
    bm_gamma = save_bookmark(
        name="gamma",
        goal="gamma goal",
        source="codex",
        config=config,
        cwd=str(repo),
    )

    db_path = tmp_path / "bookmarks.db"
    conn = open_db(db_path)

    # ------------------------------------------------------------------
    # 1. list_bookmarks returns exactly 3 rows with correct sources
    # ------------------------------------------------------------------
    all_bms = list_bookmarks(conn, include_auto=False, n=100)
    assert len(all_bms) == 3, f"Expected 3 bookmarks, got {len(all_bms)}"

    sources = {bm.source for bm in all_bms}
    assert "claude-code" in sources
    assert "cursor" in sources
    assert "codex" in sources

    # Verify names
    names = {bm.name for bm in all_bms}
    assert names == {"alpha", "beta", "gamma"}

    # ------------------------------------------------------------------
    # 2. list_bookmarks(source="cursor") returns exactly 1 row
    # ------------------------------------------------------------------
    cursor_bms = list_bookmarks(conn, source="cursor", include_auto=False, n=100)
    assert len(cursor_bms) == 1, f"Expected 1 cursor bookmark, got {len(cursor_bms)}"
    assert cursor_bms[0].source == "cursor"
    assert cursor_bms[0].name == "beta"

    # ------------------------------------------------------------------
    # 3. Direct sqlite3 query: exactly 1 bookmarks table with 3 rows
    # ------------------------------------------------------------------
    raw_conn = sqlite3.connect(str(db_path))
    tables = {
        row[0]
        for row in raw_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bookmarks'"
        ).fetchall()
    }
    assert len(tables) == 1, "There should be exactly 1 bookmarks table"

    row_count = raw_conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
    assert row_count == 3, f"Expected 3 rows in bookmarks, got {row_count}"
    raw_conn.close()

    conn.close()

    # ------------------------------------------------------------------
    # 4. show_bookmark renders same structure for all 3 (no error)
    # ------------------------------------------------------------------
    # show_bookmark returns the Bookmark object — just check it doesn't raise
    bm_show_alpha = show_bookmark(name="alpha", config=config)
    assert bm_show_alpha.name == "alpha"
    assert bm_show_alpha.source == "claude-code"

    bm_show_gamma = show_bookmark(name="gamma", config=config)
    assert bm_show_gamma.name == "gamma"
    assert bm_show_gamma.source == "codex"
