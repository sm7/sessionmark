"""Bookmark search logic for bookmark-cli — §19 Week 3.

Wraps the FTS5 search in storage/db.py and renders results via Rich.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from bookmark.config import Config
from bookmark.storage.db import open_db, search_bookmarks


def _relative_time(ts: int) -> str:
    diff = int(time.time()) - ts
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


def search_cmd(
    query: str,
    as_json: bool = False,
    limit: int = 10,
    config: Optional[Config] = None,
) -> list:
    """Full-text search over bookmark names, goals, and tags.

    Returns a list of dicts with keys: name, when, snippet, score.
    Prints results to stdout if not called programmatically.
    """
    if config is None:
        from bookmark.config import load_config
        config = load_config()

    db_path = config.home / "bookmarks.db"
    conn = open_db(db_path)

    try:
        pairs = search_bookmarks(conn, query, limit=limit)
    except Exception:
        # FTS5 query syntax error or empty table
        pairs = []
    finally:
        conn.close()

    results = [
        {
            "name": bm.name,
            "when": _relative_time(bm.created_at),
            "snippet": snippet,
            "goal": bm.goal,
        }
        for bm, snippet in pairs
    ]

    if as_json:
        print(json.dumps(results, indent=2))
        return results

    if not results:
        from rich.console import Console
        Console().print("[dim]No results.[/dim]")
        return results

    from rich.console import Console
    console = Console()
    for r in results:
        when = r["when"]
        name = r["name"]
        snippet = r["snippet"] or r.get("goal") or ""
        console.print(f"[bold white]{name}[/bold white]  [dim]{when}[/dim]  — {snippet}")

    return results
