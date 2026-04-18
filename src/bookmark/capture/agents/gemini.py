"""Gemini CLI fallback session reader — §11.7 of design doc.

Session location TBD — surfaced in `bookmark doctor` as per §17.
This implementation searches common locations.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _candidate_dirs(_base_dir: Path | None = None) -> list[Path]:
    home = _base_dir if _base_dir is not None else Path.home()
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        xdg_path = Path(xdg).expanduser() / "gemini" / "sessions"
    else:
        xdg_path = home / ".config" / "gemini" / "sessions"
    return [
        home / ".gemini" / "sessions",
        home / ".config" / "gemini" / "sessions",
        xdg_path,
    ]


def read_recent_transcript(
    cwd: str,
    n_messages: int = 20,
    _base_dir: Path | None = None,
) -> list[dict]:
    for sessions_dir in _candidate_dirs(_base_dir):
        if not sessions_dir.exists():
            continue
        files = sorted(
            sessions_dir.glob("*.jsonl"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not files:
            continue
        messages = []
        try:
            with files[0].open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        role = obj.get("role", "")
                        content = obj.get("content") or obj.get("text", "")
                        if role and content:
                            role = "user" if role in ("user", "human") else "assistant"
                            messages.append({"role": role, "content": str(content)})
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
        return messages[-n_messages:]
    return []
