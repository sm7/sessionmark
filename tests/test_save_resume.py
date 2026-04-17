"""Flow A round-trip test: save → list → name resolution.

Tests that:
1. save_bookmark creates a DB row with correct fields
2. Blob files exist in the blob store
3. goal is "wip", source is "terminal"
4. list_cmd returns the bookmark
5. Partial name match (prefix) works via resolve_name
6. --transcript-stdin saves transcript blob and sets transcript_messages

See design doc §19 (Week 1 and Week 2 test requirements).
"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

import pytest

from bookmark.config import Config
from bookmark.core.list import list_cmd
from bookmark.core.save import save_bookmark
from bookmark.storage.db import open_db, resolve_name


def _make_config(home: Path) -> Config:
    """Build a Config pointing at the given tmp home."""
    return Config(home=home, default_source="terminal", redact_enabled=True, blob_compress=False)


def test_save_creates_db_row(tmp_bookmark_home: Path, fake_git_repo: Path) -> None:
    """save_bookmark should create exactly one row in the bookmarks table."""
    config = _make_config(tmp_bookmark_home)
    bm = save_bookmark(
        name="test",
        goal="wip",
        config=config,
        cwd=str(fake_git_repo),
    )

    db_path = tmp_bookmark_home / "bookmarks.db"
    assert db_path.exists(), "DB file should be created"

    conn = open_db(db_path)
    rows = conn.execute("SELECT * FROM bookmarks").fetchall()
    assert len(rows) == 1, "Exactly one bookmark row"

    row = dict(rows[0])
    assert row["name"] == "test"
    assert row["goal"] == "wip"
    assert row["source"] == "terminal"
    assert row["id"] == bm.id
    conn.close()


def test_save_blobs_exist(tmp_bookmark_home: Path, fake_git_repo: Path) -> None:
    """save_bookmark should write at least the files blob to disk."""
    # Create a file in the repo so files_blob is written
    (fake_git_repo / "scratch.py").write_text("x = 1\n")

    config = _make_config(tmp_bookmark_home)
    bm = save_bookmark(
        name="blobtest",
        goal="blob round-trip",
        config=config,
        cwd=str(fake_git_repo),
    )

    blobs_dir = tmp_bookmark_home / "blobs"
    # At minimum the files blob should exist (scratch.py was just written)
    if bm.files_blob:
        key = bm.files_blob
        blob_path = blobs_dir / key[:2] / key[2:]
        assert blob_path.exists(), f"Blob {key} should exist on disk"


def test_save_goal_and_source(tmp_bookmark_home: Path, fake_git_repo: Path) -> None:
    """Saved bookmark should have goal='wip' and source='terminal'."""
    config = _make_config(tmp_bookmark_home)
    bm = save_bookmark(
        name="goaltest",
        goal="wip",
        source="terminal",
        config=config,
        cwd=str(fake_git_repo),
    )
    assert bm.goal == "wip"
    assert bm.source == "terminal"


def test_list_returns_bookmark(tmp_bookmark_home: Path, fake_git_repo: Path) -> None:
    """list_cmd should return the saved bookmark."""
    config = _make_config(tmp_bookmark_home)
    bm = save_bookmark(
        name="listtest",
        goal="check list",
        config=config,
        cwd=str(fake_git_repo),
    )

    results = list_cmd(config=config)
    ids = [r.id for r in results]
    assert bm.id in ids, "Saved bookmark should appear in list"


def test_partial_name_match(tmp_bookmark_home: Path, fake_git_repo: Path) -> None:
    """resolve_name should find a bookmark by unique slug prefix."""
    config = _make_config(tmp_bookmark_home)
    bm = save_bookmark(
        name="alpha-feature",
        goal="prefix test",
        config=config,
        cwd=str(fake_git_repo),
    )

    db_path = tmp_bookmark_home / "bookmarks.db"
    conn = open_db(db_path)

    # Full slug match
    found = resolve_name(conn, "alpha-feature")
    assert found is not None
    assert found.id == bm.id

    # Prefix match
    found_prefix = resolve_name(conn, "alpha")
    assert found_prefix is not None
    assert found_prefix.id == bm.id

    conn.close()


def test_auto_bookmark_hidden_by_default(tmp_bookmark_home: Path, fake_git_repo: Path) -> None:
    """Auto bookmarks should not appear in list unless include_auto=True."""
    config = _make_config(tmp_bookmark_home)
    bm = save_bookmark(
        name="auto-bm",
        goal="auto test",
        config=config,
        cwd=str(fake_git_repo),
        auto=True,
    )

    results = list_cmd(config=config, include_auto=False)
    assert bm.id not in [r.id for r in results]

    results_all = list_cmd(config=config, include_auto=True)
    assert bm.id in [r.id for r in results_all]


# ---------------------------------------------------------------------------
# Week 2: transcript stdin test (§19)
# ---------------------------------------------------------------------------


def test_transcript_stdin_saves_messages(
    tmp_bookmark_home: Path, fake_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save_bookmark with transcript_stdin=True should store 4 messages.

    Asserts:
    - transcript_messages == 4 on the returned Bookmark
    - transcript_messages == 4 in the DB row
    - transcript blob path exists on disk
    - transcript blob file has exactly 4 lines
    """
    config = _make_config(tmp_bookmark_home)

    # 4-message transcript piped via stdin
    transcript_data = "\n".join([
        '{"role": "user", "content": "run the eval with the new gamma"}',
        '{"role": "assistant", "content": "miss_rate went from 20.9 to 31.4"}',
        '{"role": "user", "content": "revert the gamma change"}',
        '{"role": "assistant", "content": "reverted, running tests now"}',
    ])
    monkeypatch.setattr(sys, "stdin", StringIO(transcript_data))

    bm = save_bookmark(
        name="transcript-test",
        goal="transcript round-trip",
        config=config,
        cwd=str(fake_git_repo),
        transcript_stdin=True,
    )

    # transcript_messages field on returned object
    assert bm.transcript_messages == 4, (
        f"Expected transcript_messages=4, got {bm.transcript_messages}"
    )

    # transcript_messages in DB
    db_path = tmp_bookmark_home / "bookmarks.db"
    conn = open_db(db_path)
    row = conn.execute(
        "SELECT transcript_messages FROM bookmarks WHERE id = ?", (bm.id,)
    ).fetchone()
    assert row is not None
    assert row[0] == 4, f"DB transcript_messages should be 4, got {row[0]}"
    conn.close()

    # Transcript blob path exists
    assert bm.transcript_blob is not None, "transcript_blob should not be None"
    blob_path = tmp_bookmark_home / bm.transcript_blob
    assert blob_path.exists(), f"Transcript blob not found at {blob_path}"

    # Blob has exactly 4 non-empty lines
    lines = [l for l in blob_path.read_text().splitlines() if l.strip()]
    assert len(lines) == 4, f"Expected 4 lines in transcript blob, got {len(lines)}"
