"""Codex CLI fallback session reader — §11.7 of design doc.

Session files at ~/.codex/sessions/ (verified from Codex CLI source).
Format: JSONL with role/content messages.
"""

from __future__ import annotations

import json
from pathlib import Path


def read_recent_transcript(
    cwd: str,
    n_messages: int | None = None,
    _base_dir: Path | None = None,
) -> list[dict]:
    """Find most recent Codex session and return last n messages.

    _base_dir: override home directory for testing.
    """
    home = _base_dir if _base_dir is not None else Path.home()
    sessions_dir = home / ".codex" / "sessions"
    if not sessions_dir.exists():
        return []

    # Find most recently modified session file
    session_files = sorted(
        sessions_dir.glob("*.jsonl"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if not session_files:
        return []

    messages = []
    try:
        with session_files[0].open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                role = obj.get("role", "")
                content = obj.get("content", "")
                if role in ("user", "assistant", "human") and content:
                    role = "user" if role == "human" else role
                    messages.append({"role": role, "content": str(content)})
    except OSError:
        pass
    return messages if n_messages is None else messages[-n_messages:]
