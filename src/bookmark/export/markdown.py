"""Markdown export for bookmark-cli — §11.5 of design doc.

Simple markdown dump of bookmark fields without Jinja2 templating.
"""

from __future__ import annotations

import json
import time
from typing import Optional


def _relative_time(ts: int) -> str:
    diff = int(time.time()) - ts
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


def render_markdown(bookmark, todos, transcript, open_files) -> str:
    """Render a Markdown summary of the bookmark.

    Parameters
    ----------
    bookmark:
        Bookmark model instance.
    todos:
        List of TodoItem instances.
    transcript:
        List of message dicts.
    open_files:
        List of FileEntry instances.
    """
    lines = []
    lines.append(f"# Bookmark: {bookmark.name}")
    lines.append("")
    lines.append(f"**Saved:** {_relative_time(bookmark.created_at)}")
    lines.append(f"**Source:** {bookmark.source}")
    lines.append(f"**Repo:** `{bookmark.repo_root}`")
    if bookmark.git_branch:
        head = bookmark.git_head[:7] if bookmark.git_head else "unknown"
        lines.append(f"**Branch:** `{bookmark.git_branch}` @ `{head}`")
    lines.append("")

    lines.append("## Goal")
    lines.append(bookmark.goal or "_(no goal set)_")
    lines.append("")

    pending_todos = [t for t in todos if t.status == "pending"]
    lines.append("## Open TODOs")
    if pending_todos:
        for todo in pending_todos:
            lines.append(f"- [ ] {todo.text}")
    else:
        lines.append("_(no open TODOs)_")
    lines.append("")

    lines.append("## Open Files")
    if open_files:
        for f in open_files:
            lines.append(f"- `{f.path}` ({f.status})")
    else:
        lines.append("_(no recently modified files)_")
    lines.append("")

    if transcript:
        lines.append("## Last Exchange")
        for msg in transcript[-4:]:
            role = msg.get("role", "").title()
            content = msg.get("content", "")
            if len(content) > 300:
                content = content[:297] + "..."
            lines.append(f"**{role}:** {content}")
        lines.append("")

    return "\n".join(lines)


def export_json(name: str, config=None) -> str:
    """Export a bookmark as a JSON string suitable for import.

    Parameters
    ----------
    name:
        Bookmark name or 'latest'.
    config:
        Pre-loaded Config object (loads fresh if None).

    Returns
    -------
    str
        JSON-formatted bookmark record including todos.
    """
    if config is None:
        from bookmark.config import load_config
        config = load_config()

    from bookmark.core.resume import _load_config_and_conn, _resolve_or_exit
    from bookmark.storage.db import get_todos

    cfg, conn = _load_config_and_conn(config)
    bm = _resolve_or_exit(conn, name)
    todos = get_todos(conn, bm.id)
    conn.close()

    data = bm.model_dump()
    data["todos"] = [t.model_dump() for t in todos]
    return json.dumps(data, indent=2)
