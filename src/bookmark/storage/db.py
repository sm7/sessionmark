"""SQLite database layer for bookmark-cli.

Manages the SQLite schema defined in design doc §7, including:
- Schema creation and migrations (tracked via PRAGMA user_version)
- CRUD operations for bookmarks, todos, and env vars
- Full-text search via FTS5 virtual table

See design doc §7 for the full schema specification.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from bookmark.core.models import Bookmark, EnvVar, TodoItem

# ---------------------------------------------------------------------------
# Schema version — increment when schema changes
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 2

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS bookmarks (
    id                   TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    slug                 TEXT NOT NULL UNIQUE,
    created_at           INTEGER NOT NULL,
    repo_root            TEXT NOT NULL,
    repo_name            TEXT,
    git_branch           TEXT,
    git_head             TEXT,
    goal                 TEXT,
    tags                 TEXT,
    source               TEXT NOT NULL,
    session_id           TEXT,
    transcript_blob      TEXT,
    diff_blob            TEXT,
    files_blob           TEXT,
    auto                 INTEGER NOT NULL DEFAULT 0,
    transcript_messages  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_bookmarks_source
    ON bookmarks(source);

CREATE INDEX IF NOT EXISTS idx_bookmarks_created_at
    ON bookmarks(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_bookmarks_repo_name
    ON bookmarks(repo_name);

CREATE TABLE IF NOT EXISTS todos (
    bookmark_id TEXT    NOT NULL,
    idx         INTEGER NOT NULL,
    text        TEXT    NOT NULL,
    origin      TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    PRIMARY KEY (bookmark_id, idx),
    FOREIGN KEY (bookmark_id) REFERENCES bookmarks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS env (
    bookmark_id TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    PRIMARY KEY (bookmark_id, key),
    FOREIGN KEY (bookmark_id) REFERENCES bookmarks(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS bookmarks_fts USING fts5(
    name, goal, tags,
    content=bookmarks,
    content_rowid=rowid
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a WAL-mode connection with row_factory set."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply schema migrations as needed."""
    version: int = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < SCHEMA_VERSION:
        conn.executescript(_DDL)
        # Migration from version 1 → 2: add transcript_messages column if absent
        if version == 1:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(bookmarks)").fetchall()}
            if "transcript_messages" not in cols:
                conn.execute(
                    "ALTER TABLE bookmarks"
                    " ADD COLUMN transcript_messages INTEGER NOT NULL DEFAULT 0"
                )
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()


def open_db(db_path: Path) -> sqlite3.Connection:
    """Open (or create) the bookmark database at *db_path*, apply migrations."""
    conn = _connect(db_path)
    _migrate(conn)
    return conn


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def insert_bookmark(conn: sqlite3.Connection, bm: Bookmark) -> None:
    """Insert a Bookmark record (and its todos/env vars) into the database."""
    conn.execute(
        """
        INSERT INTO bookmarks
            (id, name, slug, created_at, repo_root, repo_name, git_branch,
             git_head, goal, tags, source, session_id, transcript_blob,
             diff_blob, files_blob, auto, transcript_messages)
        VALUES
            (:id, :name, :slug, :created_at, :repo_root, :repo_name,
             :git_branch, :git_head, :goal, :tags, :source, :session_id,
             :transcript_blob, :diff_blob, :files_blob, :auto,
             :transcript_messages)
        """,
        {
            "id": bm.id,
            "name": bm.name,
            "slug": bm.slug,
            "created_at": bm.created_at,
            "repo_root": bm.repo_root,
            "repo_name": bm.repo_name,
            "git_branch": bm.git_branch,
            "git_head": bm.git_head,
            "goal": bm.goal,
            "tags": bm.tags,
            "source": bm.source,
            "session_id": bm.session_id,
            "transcript_blob": bm.transcript_blob,
            "diff_blob": bm.diff_blob,
            "files_blob": bm.files_blob,
            "auto": int(bm.auto),
            "transcript_messages": bm.transcript_messages,
        },
    )

    for idx, todo in enumerate(bm.todos):
        conn.execute(
            """
            INSERT INTO todos (bookmark_id, idx, text, origin, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (bm.id, idx, todo.text, todo.origin, todo.status),
        )

    for ev in bm.env_vars:
        conn.execute(
            """
            INSERT INTO env (bookmark_id, key, value) VALUES (?, ?, ?)
            """,
            (bm.id, ev.key, ev.value),
        )

    # Keep FTS index up to date
    conn.execute(
        """
        INSERT INTO bookmarks_fts(rowid, name, goal, tags)
        SELECT rowid, name, goal, tags FROM bookmarks WHERE id = ?
        """,
        (bm.id,),
    )

    conn.commit()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def _row_to_bookmark(row: sqlite3.Row) -> Bookmark:
    """Convert a DB row (from bookmarks table) to a Bookmark model."""
    d = dict(row)
    d["auto"] = bool(d.get("auto", 0))
    d.setdefault("transcript_messages", 0)
    return Bookmark(**d)


def get_bookmark_by_id(conn: sqlite3.Connection, bm_id: str) -> Bookmark | None:
    """Fetch a single bookmark by exact ID."""
    row = conn.execute("SELECT * FROM bookmarks WHERE id = ?", (bm_id,)).fetchone()
    return _row_to_bookmark(row) if row else None


def list_bookmarks(
    conn: sqlite3.Connection,
    repo: str | None = None,
    tag: str | None = None,
    source: str | None = None,
    n: int = 20,
    include_auto: bool = False,
) -> list[Bookmark]:
    """Return bookmarks matching the given filters, newest first."""
    clauses: list[str] = []
    params: list = []

    if not include_auto:
        clauses.append("auto = 0")

    if repo:
        clauses.append("repo_name = ?")
        params.append(repo)

    if tag:
        clauses.append("(',' || tags || ',') LIKE ?")
        params.append(f"%,{tag},%")

    if source:
        clauses.append("source = ?")
        params.append(source)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(n)

    rows = conn.execute(
        f"SELECT * FROM bookmarks {where} ORDER BY created_at DESC LIMIT ?",
        params,
    ).fetchall()

    return [_row_to_bookmark(r) for r in rows]


def resolve_name(conn: sqlite3.Connection, name: str) -> Bookmark | None:
    """Resolve a name or prefix to a unique Bookmark.

    Resolution order:
    1. Exact slug match
    2. Exact name match (case-insensitive)
    3. Unique slug prefix match
    Returns None if no match; raises ValueError with candidates if ambiguous.
    """
    # 1. Exact slug
    row = conn.execute(
        "SELECT * FROM bookmarks WHERE slug = ?", (name,)
    ).fetchone()
    if row:
        return _row_to_bookmark(row)

    # 2. Exact name (case-insensitive)
    row = conn.execute(
        "SELECT * FROM bookmarks WHERE lower(name) = lower(?)", (name,)
    ).fetchone()
    if row:
        return _row_to_bookmark(row)

    # 3. Unique prefix
    rows = conn.execute(
        "SELECT * FROM bookmarks WHERE slug LIKE ?", (f"{name}%",)
    ).fetchall()
    if len(rows) == 1:
        return _row_to_bookmark(rows[0])
    if len(rows) > 1:
        candidates = ", ".join(dict(r)["slug"] for r in rows)
        raise ValueError(f"Ambiguous name '{name}'. Candidates: {candidates}")

    return None


def get_todos(conn: sqlite3.Connection, bookmark_id: str) -> list[TodoItem]:
    """Fetch todos for a given bookmark."""
    rows = conn.execute(
        "SELECT text, origin, status FROM todos WHERE bookmark_id = ? ORDER BY idx",
        (bookmark_id,),
    ).fetchall()
    return [TodoItem(text=r["text"], origin=r["origin"], status=r["status"]) for r in rows]


def get_env(conn: sqlite3.Connection, bookmark_id: str) -> list[EnvVar]:
    """Fetch env vars for a given bookmark."""
    rows = conn.execute(
        "SELECT key, value FROM env WHERE bookmark_id = ?", (bookmark_id,)
    ).fetchall()
    return [EnvVar(key=r["key"], value=r["value"]) for r in rows]


def search_bookmarks(
    conn: sqlite3.Connection, query: str, limit: int = 10
) -> list[tuple[Bookmark, str]]:
    """FTS5 full-text search over name + goal + tags. Returns (bookmark, snippet) pairs."""
    rows = conn.execute(
        """
        SELECT b.*, snippet(bookmarks_fts, 0, '[', ']', '...', 8) as snippet
        FROM bookmarks_fts
        JOIN bookmarks b ON b.rowid = bookmarks_fts.rowid
        WHERE bookmarks_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        snippet = d.pop("snippet", "")
        d["auto"] = bool(d.get("auto", 0))
        d.setdefault("transcript_messages", 0)
        bm = Bookmark(**d)
        results.append((bm, snippet))
    return results


def delete_bookmark(conn: sqlite3.Connection, bm_id: str) -> None:
    """Delete a bookmark and cascade to todos/env. Also removes from FTS index."""
    # Remove from FTS first (before the row is gone)
    conn.execute(
        "DELETE FROM bookmarks_fts WHERE rowid = (SELECT rowid FROM bookmarks WHERE id = ?)",
        (bm_id,),
    )
    conn.execute("DELETE FROM bookmarks WHERE id = ?", (bm_id,))
    conn.commit()


def update_fts_index(conn: sqlite3.Connection) -> None:
    """Rebuild the FTS5 index from the bookmarks table."""
    conn.execute("INSERT INTO bookmarks_fts(bookmarks_fts) VALUES('rebuild')")
    conn.commit()
