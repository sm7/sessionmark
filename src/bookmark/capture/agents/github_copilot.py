"""GitHub Copilot Chat fallback session reader — §11.7 of design doc.

Copilot Chat runs inside VS Code and stores session data in VS Code's
workspaceStorage SQLite databases (state.vscdb), same structure as Cursor
but under the 'Code' app directory.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _storage_root(_base_dir: Path | None = None) -> Path:
    home = _base_dir if _base_dir is not None else Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Code" / "User" / "workspaceStorage"
    if sys.platform == "win32":
        base = _base_dir or Path(os.environ.get("APPDATA", ""))
        return base / "Code" / "User" / "workspaceStorage"
    return home / ".config" / "Code" / "User" / "workspaceStorage"


def read_recent_transcript(
    cwd: str,
    n_messages: int = 20,
    _base_dir: Path | None = None,
) -> list[dict]:
    """Best-effort read of most recent GitHub Copilot Chat session for cwd."""
    storage = _storage_root(_base_dir)
    if not storage.exists():
        return []

    import sqlite3

    best_time = 0.0
    best_messages: list[dict] = []

    for ws_dir in storage.iterdir():
        if not ws_dir.is_dir():
            continue
        db_path = ws_dir / "state.vscdb"
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            rows = conn.execute(
                "SELECT value FROM ItemTable WHERE"
                " key LIKE '%copilot%chat%'"
                " OR key LIKE '%copilot%history%'"
                " OR key LIKE '%github.copilot%'"
                " LIMIT 10"
            ).fetchall()
            conn.close()
            for (val,) in rows:
                if not val:
                    continue
                try:
                    data = json.loads(val)
                    msgs = _extract_messages(data, n_messages)
                    if msgs:
                        mtime = db_path.stat().st_mtime
                        if mtime > best_time:
                            best_time = mtime
                            best_messages = msgs
                except Exception:
                    pass
        except Exception:
            continue

    return best_messages


def _extract_messages(data: object, n: int) -> list[dict]:
    messages: list[dict] = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("conversations") or data.get("history") or []
    else:
        items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        role = item.get("role") or item.get("type", "")
        content = item.get("content") or item.get("text") or item.get("message", "")
        if role and content and isinstance(content, str):
            role = "user" if role in ("user", "human") else "assistant"
            messages.append({"role": role, "content": content})
    return messages[-n:]
