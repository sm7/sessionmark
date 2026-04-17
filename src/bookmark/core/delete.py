"""Bookmark delete logic for bookmark-cli — §19 Week 3.

Name resolution follows design doc §8:
  exact slug → exact name (case-insensitive) → unique prefix → error exit 2
"""

from __future__ import annotations

import sys
from typing import Optional

from bookmark.config import Config
from bookmark.storage.db import delete_bookmark as _db_delete, open_db, resolve_name, list_bookmarks


def delete_bookmark(name: str, force: bool = False, config: Optional[Config] = None) -> None:
    """Delete a bookmark by name, with optional confirmation prompt.

    Parameters
    ----------
    name:
        Bookmark name, slug, or prefix to delete.
    force:
        If True, skip confirmation prompt.
    config:
        Pre-loaded Config (loads fresh if None).
    """
    import typer

    if config is None:
        from bookmark.config import load_config
        config = load_config()

    db_path = config.home / "bookmarks.db"
    conn = open_db(db_path)

    # Resolve name
    if name == "latest":
        rows = list_bookmarks(conn, n=1, include_auto=False)
        if not rows:
            print("No bookmarks found.", file=sys.stderr)
            conn.close()
            raise typer.Exit(2)
        bm = rows[0]
    else:
        try:
            bm = resolve_name(conn, name)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            conn.close()
            raise typer.Exit(1) from exc

        if bm is None:
            print(f"Bookmark '{name}' not found.", file=sys.stderr)
            conn.close()
            raise typer.Exit(2)

    if not force:
        answer = input(f"Delete '{bm.name}'? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.", file=sys.stderr)
            conn.close()
            raise typer.Exit(0)

    _db_delete(conn, bm.id)
    conn.close()
    print(f"Deleted bookmark '{bm.name}'.")
