"""Aider fallback session reader — §11.7 of design doc.

Reads .aider.chat.history.md in cwd (or cwd parents).
Format: markdown with '#### <role>' headers.
"""

from __future__ import annotations

import re
from pathlib import Path


def read_recent_transcript(cwd: str, n_messages: int | None = None) -> list[dict]:
    """Parse .aider.chat.history.md from cwd or its parents."""
    history_file = None
    for parent in [Path(cwd)] + list(Path(cwd).parents):
        candidate = parent / ".aider.chat.history.md"
        if candidate.exists():
            history_file = candidate
            break

    if not history_file:
        return []

    messages = []
    current_role = None
    current_lines: list[str] = []

    try:
        for line in history_file.read_text(encoding="utf-8", errors="replace").splitlines():
            # Aider uses #### for role headers
            header_match = re.match(r"^#### (.+)$", line)
            if header_match:
                if current_role and current_lines:
                    content = "\n".join(current_lines).strip()
                    if content:
                        messages.append({"role": current_role, "content": content})
                raw_role = header_match.group(1).strip().lower()
                current_role = "user" if raw_role in ("human", "user") else "assistant"
                current_lines = []
            else:
                if current_role is not None:
                    current_lines.append(line)

        if current_role and current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                messages.append({"role": current_role, "content": content})
    except OSError:
        pass

    return messages if n_messages is None else messages[-n_messages:]
