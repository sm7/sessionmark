"""Bookmark save orchestration for bookmark-cli.

Orchestrates the full capture → redact → write pipeline:
1. Capture git context, recently modified files, todos, env vars
2. Read transcript from stdin (if --transcript-stdin)
3. Redact secrets from all text blobs
4. Write blobs to content-addressed blob store
5. Write the bookmark row (+ todos + env) to SQLite
6. Print a one-line confirmation

See design doc §6 for the save pipeline description.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from bookmark.capture.env import capture_env
from bookmark.capture.files import capture_files
from bookmark.capture.git import capture_git
from bookmark.capture.shell import capture_shell_history
from bookmark.capture.todos import capture_todos
from bookmark.config import Config
from bookmark.core.models import Bookmark, TodoItem, make_id
from bookmark.redact import redact
from bookmark.storage.blobs import BlobStore
from bookmark.storage.db import insert_bookmark, open_db


def _slugify(name: str) -> str:
    """Convert a human name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "bookmark"


def _unique_slug(conn, base_slug: str) -> str:
    """Return a slug that is unique in the DB (append -N suffix if needed)."""
    slug = base_slug
    n = 1
    while True:
        row = conn.execute("SELECT id FROM bookmarks WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            return slug
        slug = f"{base_slug}-{n}"
        n += 1


def _normalize_role(role: str) -> str:
    """Normalize agent-specific role names to canonical user/assistant."""
    role = role.lower().strip()
    if role in ("human", "user"):
        return "user"
    if role in ("ai", "assistant", "bot", "agent"):
        return "assistant"
    return role


_TODO_PATTERNS = [
    re.compile(r"TODO:\s*(.+)", re.IGNORECASE),
    re.compile(r"\[ \]\s*(.+)"),
    re.compile(r"\[x\]\s*(.+)", re.IGNORECASE),
]


def _extract_todos_from_transcript(messages: list[dict]) -> list[TodoItem]:
    """Extract TODO items from assistant messages in the transcript."""
    todos: list[TodoItem] = []
    for msg in messages:
        role = _normalize_role(msg.get("role", ""))
        if role != "assistant":
            continue
        content = msg.get("content", "")
        if not isinstance(content, str):
            continue
        for line in content.splitlines():
            for pat in _TODO_PATTERNS:
                m = pat.search(line)
                if m:
                    text = m.group(1).strip()
                    if text:
                        # Determine status from [x] pattern
                        status = (
                            "done" if re.match(r"\[x\]", line.strip(), re.IGNORECASE)
                            else "pending"
                        )
                        todos.append(TodoItem(text=text, origin="agent", status=status))
                    break
    return todos


def _read_transcript_from_stdin() -> list[dict]:
    """Read JSON-lines from stdin, normalize roles, skip malformed lines."""
    messages: list[dict] = []
    for line in sys.stdin.read().strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            print("[bookmark] warning: skipping malformed transcript line", file=sys.stderr)
            continue
        if not isinstance(msg, dict):
            continue
        # Normalize role
        raw_role = msg.get("role", "")
        msg["role"] = _normalize_role(raw_role)
        messages.append(msg)
    return messages


def _write_transcript_blob(
    config: Config,
    bookmark_id: str,
    messages: list[dict],
) -> str:
    """Write transcript as JSONL to blobs/tr/<id>/transcript.jsonl.

    Returns the blob path (relative to bookmark home) used as transcript_blob key.
    """
    # Build JSONL content — one redacted JSON object per line
    lines: list[str] = []
    for msg in messages:
        clean = dict(msg)
        # Redact content field
        if isinstance(clean.get("content"), str):
            clean["content"] = redact(clean["content"])
        lines.append(json.dumps(clean, ensure_ascii=False))
    jsonl_content = "\n".join(lines) + "\n"

    # Store in a named path under blobs/tr/<id>/transcript.jsonl
    blob_dir = config.home / "blobs" / "tr" / bookmark_id
    blob_dir.mkdir(parents=True, exist_ok=True)
    blob_path = blob_dir / "transcript.jsonl"
    blob_path.write_text(jsonl_content, encoding="utf-8")

    # Return relative path as the blob key (so it can be looked up later)
    return str(blob_path.relative_to(config.home))


def save_bookmark(
    name: str,
    goal: str | None = None,
    tags: str | None = None,
    source: str | None = None,
    transcript_stdin: bool = False,
    cwd: str | None = None,
    config: Config | None = None,
    auto: bool = False,
) -> Bookmark:
    """Run the full save pipeline and return the saved Bookmark.

    Parameters
    ----------
    name:
        Human-readable bookmark name (e.g. "wip", "auth-refactor").
    goal:
        Short description of the current goal (-m / --msg flag).
    tags:
        Comma-separated tag string.
    source:
        Agent source identifier (default from config or "terminal").
    transcript_stdin:
        If True, read JSON-lines transcript from stdin.
    cwd:
        Working directory to capture (default: os.getcwd()).
    config:
        Pre-loaded Config object (loads fresh if None).
    auto:
        True for hook-triggered bookmarks (hidden in list by default).
    """
    if config is None:
        from bookmark.config import load_config
        config = load_config()

    if source is None:
        source = config.default_source

    effective_cwd = cwd or os.getcwd()

    # ------------------------------------------------------------------
    # 1. Capture
    # ------------------------------------------------------------------
    git_info = capture_git(cwd=effective_cwd)
    file_entries = capture_files(cwd=effective_cwd)
    recently_modified = [f.path for f in file_entries]
    todos = capture_todos(cwd=effective_cwd, recently_modified=recently_modified)
    env_vars = capture_env(cwd=effective_cwd)

    # Shell history — store as a special env entry (key "shell_history", JSON array)
    shell_cmds = capture_shell_history()
    if shell_cmds:
        from bookmark.core.models import EnvVar as _EnvVar
        env_vars.append(_EnvVar(key="shell_history", value=json.dumps(shell_cmds)))

    # ------------------------------------------------------------------
    # 2. Transcript (optional) — §19 Week 2
    # ------------------------------------------------------------------
    transcript_blob_key: str | None = None
    n_msgs = 0
    transcript_todos: list[TodoItem] = []

    if transcript_stdin:
        messages = _read_transcript_from_stdin()
        n_msgs = len(messages)
        if messages:
            # Extract TODOs from transcript before writing
            transcript_todos = _extract_todos_from_transcript(messages)

            # Generate ID first so we can use it in the path
            bm_id = make_id()

            # Write transcript blob at named path
            transcript_blob_key = _write_transcript_blob(config, bm_id, messages)
        else:
            bm_id = make_id()
    else:
        bm_id = make_id()

    # Try fallback session-file reader if no transcript captured yet
    if not transcript_stdin and n_msgs == 0:
        try:
            from bookmark.capture.agents import get_agent_reader
            reader = get_agent_reader(source)
            if reader:
                fallback_msgs = reader.read_recent_transcript(effective_cwd)
                if fallback_msgs:
                    n_msgs = len(fallback_msgs)
                    transcript_todos = _extract_todos_from_transcript(fallback_msgs)
                    transcript_blob_key = _write_transcript_blob(config, bm_id, fallback_msgs)
        except Exception:
            pass  # fallback is best-effort, never crash save

    # Merge transcript TODOs (deduplicated by text)
    existing_todo_texts = {t.text for t in todos}
    for t in transcript_todos:
        if t.text not in existing_todo_texts:
            todos.append(t)
            existing_todo_texts.add(t.text)

    # ------------------------------------------------------------------
    # 3. Files blob
    # ------------------------------------------------------------------
    blobs = BlobStore(config.home, compress=config.blob_compress)
    files_blob_key: str | None = None
    if file_entries:
        raw_files = json.dumps(
            [e.model_dump() for e in file_entries], indent=2
        )
        clean_files = redact(raw_files)
        files_blob_key = blobs.write(clean_files)

    # ------------------------------------------------------------------
    # 4. Diff blob
    # ------------------------------------------------------------------
    diff_blob_key: str | None = None
    if git_info.modified_files:
        raw_diff = json.dumps(
            [f.model_dump() for f in git_info.modified_files], indent=2
        )
        clean_diff = redact(raw_diff)
        diff_blob_key = blobs.write(clean_diff)

    # ------------------------------------------------------------------
    # 5. Redact plaintext fields before any persistence
    # ------------------------------------------------------------------
    # goal and tags go into SQLite — must be clean
    clean_goal = redact(goal) if goal else goal
    clean_tags = redact(tags) if tags else tags

    # Redact each todo's text (origin + status are internal, not user-supplied)
    for t in todos:
        t.text = redact(t.text)

    # Redact env var values (keys are always safe internal identifiers)
    for ev in env_vars:
        ev.value = redact(ev.value)

    # ------------------------------------------------------------------
    # 6. Build Bookmark model
    # ------------------------------------------------------------------
    db_path = config.home / "bookmarks.db"
    conn = open_db(db_path)

    base_slug = _slugify(name)
    slug = _unique_slug(conn, base_slug)

    bm = Bookmark(
        id=bm_id,
        name=name,
        slug=slug,
        created_at=int(time.time()),
        repo_root=git_info.repo_root or effective_cwd,
        repo_name=git_info.repo_name,
        git_branch=git_info.branch,
        git_head=git_info.head,
        goal=clean_goal,
        tags=clean_tags,
        source=source,
        transcript_blob=transcript_blob_key,
        diff_blob=diff_blob_key,
        files_blob=files_blob_key,
        auto=auto,
        todos=todos,
        env_vars=env_vars,
        transcript_messages=n_msgs,
    )

    # ------------------------------------------------------------------
    # 7. Persist
    # ------------------------------------------------------------------
    insert_bookmark(conn, bm)
    conn.close()

    # ------------------------------------------------------------------
    # 8. Inject context into installed agent config files (best-effort)
    # ------------------------------------------------------------------
    try:
        from bookmark.install.context_writer import update_all_installed

        session_data = bm.model_dump()
        session_data["todos"] = [t.model_dump() for t in todos]
        update_all_installed(Path(effective_cwd), session_data)
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 9. Confirm
    # ------------------------------------------------------------------
    n_files = len(file_entries)
    n_todos = len(todos)
    print(
        f"✓ bookmarked {name} "
        f"(session {bm.id[:8]}..., {n_files} files, {n_msgs} msgs, {n_todos} todos)"
    )

    return bm
