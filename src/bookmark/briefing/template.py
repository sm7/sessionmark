"""Template-mode briefing generator — §10 of design doc. Deterministic, zero-LLM.

Assembles a human-readable briefing from stored bookmark fields.
No external calls, no LLM. Output is rich-formatted text.

See design doc §10 for the full briefing format specification.
"""

from __future__ import annotations

import time

from bookmark.core.models import Bookmark, FileEntry, TodoItem


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


def _last_exchange(transcript: list[dict]) -> tuple[str | None, str | None]:
    """Extract the last user message and last assistant message from transcript."""
    last_user: str | None = None
    last_assistant: str | None = None
    for msg in transcript:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        if role == "user":
            last_user = content
        elif role == "assistant":
            last_assistant = content
    return last_user, last_assistant


def _truncate(s: str, n: int) -> str:
    """Truncate string to at most n characters, adding ellipsis if needed."""
    if len(s) <= n:
        return s
    return s[:n - 1] + "…"


def _next_step_heuristic(last_assistant: str | None, max_chars: int = 120) -> str:
    """Extract a 'next step' hint from the last assistant message.

    Looks for the last imperative sentence (ends with '.' or '?').
    Falls back to last 20 words if none found.
    """
    if not last_assistant:
        return ""

    text = last_assistant.strip()
    # Split on sentence-ending punctuation
    sentences = [s.strip() for s in __import__("re").split(r"(?<=[.?!])\s+", text) if s.strip()]

    # Find last sentence ending with . or ?
    for sentence in reversed(sentences):
        if sentence.endswith((".","?")):
            return _truncate(sentence, max_chars)

    # Fallback: last 20 words
    words = text.split()
    return " ".join(words[-20:]) if words else ""


def render_briefing(
    bookmark: Bookmark,
    todos: list[TodoItem],
    transcript: list[dict],
    open_files: list[FileEntry],
    include_next_step: bool = True,
    full_transcript: bool = False,
    llm_summary: str | None = None,
) -> str:
    """Render a briefing from stored fields. No LLM.

    Parameters
    ----------
    bookmark:
        The Bookmark record to render.
    todos:
        List of TodoItem objects for this bookmark.
    transcript:
        List of message dicts (role, content, ...).
    open_files:
        List of FileEntry objects captured at save time.
    include_next_step:
        If True, include the NEXT STEP section (used by `resume`, not `show`).
    full_transcript:
        If True, include all transcript messages rather than just last exchange.
    """
    lines: list[str] = []

    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------
    relative = _relative_time(bookmark.created_at)
    header = f"📍 {bookmark.name}  saved {relative}"
    lines.append(header)

    # Repo line
    repo_line = bookmark.repo_root
    if bookmark.git_branch:
        head_short = (bookmark.git_head or "")[:7]
        if head_short:
            repo_line += f"  on {bookmark.git_branch} @ {head_short}"
        else:
            repo_line += f"  on {bookmark.git_branch}"
    lines.append(repo_line)
    lines.append("")

    # -----------------------------------------------------------------------
    # SUMMARY (LLM) or GOAL (template)
    # -----------------------------------------------------------------------
    if llm_summary:
        lines.append("SUMMARY")
        for sentence in llm_summary.strip().splitlines():
            lines.append(f"  {sentence}")
        lines.append("")
    elif bookmark.goal:
        lines.append("GOAL")
        lines.append(f"  {bookmark.goal}")
        lines.append("")

    # -----------------------------------------------------------------------
    # LAST AGENT EXCHANGE (only if transcript available)
    # -----------------------------------------------------------------------
    if transcript:
        if full_transcript:
            lines.append(f"TRANSCRIPT ({len(transcript)} messages)")
            for msg in transcript:
                role_label = "  you  " if msg.get("role") == "user" else "  agent"
                content = msg.get("content", "")
                if not isinstance(content, str):
                    content = str(content)
                lines.append(f"{role_label} → {_truncate(content, 200)}")
            lines.append("")
        else:
            last_user, last_assistant = _last_exchange(transcript)
            if last_user or last_assistant:
                lines.append("LAST AGENT EXCHANGE")
                if last_user:
                    lines.append(f"  you   → {_truncate(last_user, 120)}")
                if last_assistant:
                    lines.append(f"  agent → {_truncate(last_assistant, 120)}")
                lines.append("")

    # -----------------------------------------------------------------------
    # TODOS
    # -----------------------------------------------------------------------
    if todos:
        pending = [t for t in todos if t.status == "pending"]
        done = [t for t in todos if t.status == "done"]
        lines.append(f"TODOS ({len(pending)} pending)")
        for t in pending:
            lines.append(f"  [ ] {t.text}")
        for t in done:
            lines.append(f"  [x] {t.text}")
        lines.append("")

    # -----------------------------------------------------------------------
    # OPEN FILES
    # -----------------------------------------------------------------------
    if open_files:
        lines.append(f"OPEN FILES ({len(open_files)})")
        for f in open_files:
            lines.append(f"  {f.status}  {f.path}")
        lines.append("")

    # -----------------------------------------------------------------------
    # NEXT STEP (resume only)
    # -----------------------------------------------------------------------
    if include_next_step:
        lines.append("NEXT STEP")
        cmd_parts = [f"cd {bookmark.repo_root}"]
        if bookmark.git_branch:
            cmd_parts.append(f"git checkout {bookmark.git_branch}")
        lines.append(f"  {' && '.join(cmd_parts)}")
        lines.append("")

    return "\n".join(lines)
