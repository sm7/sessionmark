"""Tests for the storage layer (DB schema + blob store).

Verifies:
1. DB schema is created correctly (all tables present)
2. Migration version is set to SCHEMA_VERSION after first open
3. Blob write/read round-trip (with and without compression)

See design doc §7 and §10 for storage design.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bookmark.storage.blobs import BlobStore
from bookmark.storage.db import SCHEMA_VERSION, open_db


# ---------------------------------------------------------------------------
# DB tests
# ---------------------------------------------------------------------------


def test_db_schema_created(tmp_path: Path) -> None:
    """All required tables should exist after open_db."""
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow') "
            "OR type = 'table'"
        ).fetchall()
    }
    assert "bookmarks" in tables
    assert "todos" in tables
    assert "env" in tables
    # FTS virtual table
    assert "bookmarks_fts" in tables
    conn.close()


def test_db_migration_version(tmp_path: Path) -> None:
    """PRAGMA user_version should equal SCHEMA_VERSION after open_db."""
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == SCHEMA_VERSION
    conn.close()


def test_db_indexes_created(tmp_path: Path) -> None:
    """Expected indexes should exist after schema creation."""
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)

    indexes = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    assert "idx_bookmarks_source" in indexes
    assert "idx_bookmarks_created_at" in indexes
    assert "idx_bookmarks_repo_name" in indexes
    conn.close()


def test_db_idempotent_schema(tmp_path: Path) -> None:
    """Calling open_db twice on the same path should not raise."""
    db_path = tmp_path / "test.db"
    conn1 = open_db(db_path)
    conn1.close()
    conn2 = open_db(db_path)
    conn2.close()


# ---------------------------------------------------------------------------
# Blob store tests
# ---------------------------------------------------------------------------


def test_blob_write_read_roundtrip_compressed(tmp_path: Path) -> None:
    """BlobStore.write/read should preserve content with compression."""
    store = BlobStore(tmp_path, compress=True)
    content = "Hello, blob store! " * 100
    key = store.write(content)
    assert len(key) == 64  # SHA-256 hex
    result = store.read(key)
    assert result == content


def test_blob_write_read_roundtrip_uncompressed(tmp_path: Path) -> None:
    """BlobStore.write/read should preserve content without compression."""
    store = BlobStore(tmp_path, compress=False)
    content = "Plain text blob content.\n" * 50
    key = store.write(content)
    result = store.read(key)
    assert result == content


def test_blob_exists(tmp_path: Path) -> None:
    """BlobStore.exists should return True after write and False before."""
    store = BlobStore(tmp_path, compress=False)
    content = "check exists"
    key = store.write(content)
    assert store.exists(key) is True
    fake_key = "a" * 64
    assert store.exists(fake_key) is False


def test_blob_write_idempotent(tmp_path: Path) -> None:
    """Writing the same content twice should return the same key."""
    store = BlobStore(tmp_path, compress=False)
    content = "duplicate content"
    key1 = store.write(content)
    key2 = store.write(content)
    assert key1 == key2


def test_blob_read_missing_returns_none(tmp_path: Path) -> None:
    """Reading a non-existent key should return None."""
    store = BlobStore(tmp_path, compress=False)
    result = store.read("0" * 64)
    assert result is None


def test_blob_path_structure(tmp_path: Path) -> None:
    """Blobs should be stored in <home>/blobs/<key[:2]>/<key[2:]>."""
    store = BlobStore(tmp_path, compress=False)
    content = "path structure test"
    key = store.write(content)
    expected = tmp_path / "blobs" / key[:2] / key[2:]
    assert expected.exists()
