"""Import bookmarks from an exported JSON file — sessionmark import FILE."""

from __future__ import annotations

import json
from pathlib import Path

from bookmark.config import Config


def import_bookmarks(file_path: str, config: Config | None = None) -> int:
    """Import bookmarks from a JSON file. Returns count imported.

    The JSON file should contain either:
    - A single bookmark dict (as produced by export --format json)
    - A list of bookmark dicts

    Bookmarks whose slug already exists in the database are skipped.
    """
    if config is None:
        from bookmark.config import load_config
        config = load_config()

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Import file not found: {file_path}")

    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)

    # Normalize to list
    if isinstance(data, dict):
        records = [data]
    elif isinstance(data, list):
        records = data
    else:
        raise ValueError(f"Expected a JSON object or array, got {type(data).__name__}")

    from bookmark.core.models import Bookmark, TodoItem
    from bookmark.storage.db import insert_bookmark, open_db

    db_path = config.home / "bookmarks.db"
    conn = open_db(db_path)

    imported = 0
    for record in records:
        if not isinstance(record, dict):
            print("skipped: invalid record (not a dict)")
            continue

        slug = record.get("slug") or record.get("name", "")
        if not slug:
            print("skipped: record has no slug or name")
            continue

        # Check if slug already exists
        existing = conn.execute(
            "SELECT id FROM bookmarks WHERE slug = ?", (slug,)
        ).fetchone()
        if existing:
            print(f"skipped: {slug} already exists")
            continue

        # Build Bookmark from the record
        # Strip out fields that aren't part of the Bookmark schema
        todos_raw = record.pop("todos", [])
        # env_vars may be in the record
        env_vars_raw = record.pop("env_vars", [])

        # Handle transcript_messages default
        record.setdefault("transcript_messages", 0)
        record.setdefault("source", "generic")
        record.setdefault("auto", False)

        try:
            # Convert todos
            from bookmark.core.models import EnvVar
            todos = [
                TodoItem(
                    text=t.get("text", ""),
                    origin=t.get("origin", "import"),
                    status=t.get("status", "pending"),
                )
                for t in todos_raw
                if isinstance(t, dict)
            ]
            env_vars = [
                EnvVar(key=e.get("key", ""), value=e.get("value", ""))
                for e in env_vars_raw
                if isinstance(e, dict) and e.get("key")
            ]

            bm = Bookmark(**record, todos=todos, env_vars=env_vars)
            insert_bookmark(conn, bm)
            imported += 1
            print(f"imported: {slug}")
        except Exception as exc:
            print(f"skipped: {slug} — {exc}")

    conn.close()
    return imported
