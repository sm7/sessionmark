"""Cursor fallback session reader — §11.7 of design doc.

Cursor session data in ~/Library/Application Support/Cursor/User/workspaceStorage/ (macOS).
Format is SQLite; best-effort read.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def read_recent_transcript(
    cwd: str,
    n_messages: int | None = None,
    _base_dir: Path | None = None,
) -> list[dict]:
    """Best-effort read of most recent Cursor session for cwd."""
    if sys.platform == "darwin":
        base = _base_dir if _base_dir is not None else Path.home()
        storage = base / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage"
    elif sys.platform == "win32":
        if _base_dir is not None:
            storage = _base_dir / "Cursor" / "User" / "workspaceStorage"
        else:
            storage = Path(os.environ.get("APPDATA", "")) / "Cursor" / "User" / "workspaceStorage"
    else:
        if _base_dir is not None:
            storage = _base_dir / ".config" / "Cursor" / "User" / "workspaceStorage"
        else:
            storage = Path.home() / ".config" / "Cursor" / "User" / "workspaceStorage"

    if not storage.exists():
        return []

    import sqlite3
    best_time = 0
    best_messages: list[dict] = []

    for ws_dir in storage.iterdir():
        if not ws_dir.is_dir():
            continue
        db_path = ws_dir / "state.vscdb"
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            # Cursor stores chat in ItemTable key-value store
            rows = conn.execute(
                "SELECT value FROM ItemTable"
                " WHERE key LIKE '%aiService.prompts%' OR key LIKE '%chat%history%'"
                " LIMIT 5"
            ).fetchall()
            conn.close()
            for (val,) in rows:
                if not val:
                    continue
                import json
                try:
                    data = json.loads(val)
                    msgs = _extract_cursor_messages(data, n_messages)
                    if msgs:
                        mtime = db_path.stat().st_mtime
                        if mtime > best_time:
                            best_time = mtime
                            best_messages = msgs
                except (Exception,):
                    pass
        except Exception:
            continue

    return best_messages


def _extract_cursor_messages(data: object, n: int | None) -> list[dict]:
    """Try to extract messages from Cursor's chat history structure."""
    messages = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                role = item.get("role") or item.get("type", "")
                content = item.get("content") or item.get("text") or item.get("message", "")
                if role and content and isinstance(content, str):
                    role = "user" if role in ("user", "human") else "assistant"
                    messages.append({"role": role, "content": content})
    return messages if n is None else messages[-n:]
