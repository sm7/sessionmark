"""Claude Code fallback session reader — §11.7 of design doc.

Session files at ~/.claude/projects/<project-hash>/<session-uuid>.jsonl
Primary approach: match by cwd stored inside the jsonl itself.
Falls back to hash algorithm only if needed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def _hash_project_path(path: str) -> str:
    return hashlib.sha256(path.encode()).hexdigest()[:16]


def read_recent_transcript(
    cwd: str,
    n_messages: int = 20,
    _base_dir: Path | None = None,
) -> list[dict]:
    """Find the most recent Claude Code session for cwd and return last n messages.

    _base_dir: override home directory for testing.
    """
    home = _base_dir if _base_dir is not None else Path.home()
    claude_home = home / ".claude" / "projects"
    if not claude_home.exists():
        return []

    best_file = None
    best_mtime = 0

    # Try each project dir — match by cwd inside the jsonl
    for project_dir in claude_home.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in sorted(
            project_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True
        ):
            try:
                # Quick check: read first few lines for cwd
                with jsonl_file.open() as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        # Claude Code stores cwd in session metadata
                        session_cwd = obj.get("cwd") or obj.get("projectRoot") or ""
                        if session_cwd and os.path.normpath(session_cwd) == os.path.normpath(cwd):
                            mtime = jsonl_file.stat().st_mtime
                            if mtime > best_mtime:
                                best_mtime = mtime
                                best_file = jsonl_file
                        break  # only check first line for cwd
            except (OSError, StopIteration):
                continue

    if best_file is None:
        return []

    return _parse_jsonl_messages(best_file, n_messages)


def _parse_jsonl_messages(path: Path, n: int) -> list[dict]:
    """Parse a Claude Code JSONL session file into normalized messages."""
    messages = []
    try:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Claude Code format: {"type": "say", "say": "user"|"assistant", "text": "..."}
                # Also: {"type": "message", "role": "user"|"assistant", "content": "..."}
                role = None
                content = None
                if obj.get("type") == "say":
                    role = obj.get("say", "")
                    content = obj.get("text", "")
                elif obj.get("role") in ("user", "assistant", "human"):
                    role = obj.get("role")
                    content = obj.get("content", "")
                    if isinstance(content, list):
                        # Claude content blocks
                        content = " ".join(
                            block.get("text", "") for block in content
                            if isinstance(block, dict) and block.get("type") == "text"
                        )
                if role and content:
                    role = "user" if role in ("user", "human") else "assistant"
                    messages.append({"role": role, "content": str(content)})
    except OSError:
        pass
    return messages[-n:]
