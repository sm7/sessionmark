"""Bookmark list logic for bookmark-cli.

Queries the SQLite database and renders a Rich table with columns:
  NAME | WHEN (relative) | SOURCE | REPO | GOAL (truncated)

Auto bookmarks are hidden by default (shown with --all).

See design doc §6 for the list pipeline description.
"""

from __future__ import annotations

import json
import time

from rich.console import Console
from rich.table import Table

from bookmark.config import Config
from bookmark.core.models import Bookmark
from bookmark.storage.db import list_bookmarks, open_db


def _relative_time(ts: int) -> str:
    """Return a human-friendly relative time string."""
    diff = int(time.time()) - ts
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


def _truncate(s: str | None, n: int = 40) -> str:
    if not s:
        return ""
    return s if len(s) <= n else s[: n - 1] + "…"


def list_cmd(
    repo: str | None = None,
    tag: str | None = None,
    source: str | None = None,
    n: int = 20,
    as_json: bool = False,
    include_auto: bool = False,
    config: Config | None = None,
) -> list[Bookmark]:
    """Query bookmarks and print them (table or JSON).

    Returns the list of Bookmark objects for programmatic use.
    """
    if config is None:
        from bookmark.config import load_config
        config = load_config()

    db_path = config.home / "bookmarks.db"
    conn = open_db(db_path)

    bookmarks = list_bookmarks(
        conn,
        repo=repo,
        tag=tag,
        source=source,
        n=n,
        include_auto=include_auto,
    )
    conn.close()

    if as_json:
        data = [
            {
                "id": bm.id,
                "name": bm.name,
                "slug": bm.slug,
                "created_at": bm.created_at,
                "repo_name": bm.repo_name,
                "git_branch": bm.git_branch,
                "goal": bm.goal,
                "tags": bm.tags,
                "source": bm.source,
                "auto": bm.auto,
            }
            for bm in bookmarks
        ]
        print(json.dumps(data, indent=2))
        return bookmarks

    console = Console()
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("NAME", style="bold white", min_width=16)
    table.add_column("WHEN", style="dim", min_width=8)
    table.add_column("SOURCE", style="yellow", min_width=10)
    table.add_column("REPO", style="cyan", min_width=10)
    table.add_column("GOAL", style="white", min_width=20)

    for bm in bookmarks:
        table.add_row(
            bm.name,
            _relative_time(bm.created_at),
            bm.source,
            bm.repo_name or "",
            _truncate(bm.goal),
        )

    if bookmarks:
        console.print(table)
    else:
        console.print("[dim]No bookmarks found.[/dim]")

    return bookmarks
