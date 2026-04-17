"""Pydantic v2 data models for bookmark-cli.

These models represent the canonical in-memory representation of a bookmark
and its related records. They map 1-to-1 with the SQLite schema defined in §7.

See design doc §7 for the schema and §8 for the model design.
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from pydantic import BaseModel, Field


def make_id() -> str:
    """Generate a time-based unique ID (ULID-like) using stdlib only.

    Format: 13-char hex millisecond timestamp + 10-char random hex (upper).
    Good enough for v0.1.0 per design doc §17.
    """
    ts_part = f"{int(time.time() * 1000):013X}"
    rand_part = uuid.uuid4().hex[:10].upper()
    return f"{ts_part}{rand_part}"


# ---------------------------------------------------------------------------
# Source constants
# ---------------------------------------------------------------------------

VALID_SOURCES = frozenset(
    {"claude-code", "cursor", "codex", "gemini", "aider", "terminal", "generic"}
)


# ---------------------------------------------------------------------------
# Todo
# ---------------------------------------------------------------------------


class TodoItem(BaseModel):
    """A single to-do item captured from the workspace."""

    text: str
    origin: str  # "TODO.md" | "agent" | "comment"
    status: str = "pending"  # "pending" | "done"


# ---------------------------------------------------------------------------
# EnvVar
# ---------------------------------------------------------------------------


class EnvVar(BaseModel):
    """A captured environment variable / runtime info pair."""

    key: str
    value: str


# ---------------------------------------------------------------------------
# FileEntry
# ---------------------------------------------------------------------------


class FileEntry(BaseModel):
    """A file that was recently modified or is untracked."""

    path: str
    status: str  # git status letter, e.g. M, A, ?
    additions: int = 0
    deletions: int = 0


# ---------------------------------------------------------------------------
# GitInfo
# ---------------------------------------------------------------------------


class GitInfo(BaseModel):
    """Snapshot of the git repo state at bookmark time."""

    branch: Optional[str] = None
    head: Optional[str] = None
    repo_root: Optional[str] = None
    repo_name: Optional[str] = None
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    modified_files: list[FileEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Bookmark (the main record)
# ---------------------------------------------------------------------------


class Bookmark(BaseModel):
    """Full bookmark record — maps to the `bookmarks` table in §7."""

    id: str = Field(default_factory=make_id)
    name: str
    slug: str
    created_at: int = Field(default_factory=lambda: int(time.time()))
    repo_root: str = ""
    repo_name: Optional[str] = None
    git_branch: Optional[str] = None
    git_head: Optional[str] = None
    goal: Optional[str] = None
    tags: Optional[str] = None  # comma-separated
    source: str = "terminal"
    session_id: Optional[str] = None
    transcript_blob: Optional[str] = None
    diff_blob: Optional[str] = None
    files_blob: Optional[str] = None
    auto: bool = False
    transcript_messages: int = 0  # count of messages stored (Week 2, §19)
    # In-memory only (not stored in bookmarks table directly)
    todos: list[TodoItem] = Field(default_factory=list)
    env_vars: list[EnvVar] = Field(default_factory=list)
