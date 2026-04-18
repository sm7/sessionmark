"""TODO item capture for bookmark-cli.

Collects to-do items from multiple sources:
1. TODO.md in the project root (if it exists)
2. .claude/todos/* files (if they exist)
3. TODO: / FIXME: comments in recently modified source files

Returns a list of TodoItem objects.

See design doc §5 for capture pipeline overview.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from bookmark.core.models import TodoItem

_TODO_RE = re.compile(r"(?:TODO|FIXME)\s*(?::|)\s*(.+)", re.IGNORECASE)
_TODO_MD_ITEM = re.compile(r"[-*]\s*\[([xX ])\]\s*(.+)")  # GFM checkbox

# File extensions to scan for inline TODO comments
_SCAN_EXTENSIONS = frozenset(
    {".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs", ".rb", ".java", ".c", ".cpp"}
)


def _parse_todo_md(path: Path) -> list[TodoItem]:
    """Parse a TODO.md file with GFM-style checkboxes."""
    items: list[TodoItem] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return items

    for line in text.splitlines():
        m = _TODO_MD_ITEM.match(line.strip())
        if m:
            checked, text_content = m.group(1), m.group(2).strip()
            status = "done" if checked.lower() == "x" else "pending"
            items.append(TodoItem(text=text_content, origin="TODO.md", status=status))

    # Also include plain list items without checkboxes
    if not items:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("-", "*")) and "[" not in stripped:
                content = stripped.lstrip("-* ").strip()
                if content:
                    items.append(TodoItem(text=content, origin="TODO.md", status="pending"))

    return items


def _parse_claude_todos(base: Path) -> list[TodoItem]:
    """Parse todos from .claude/todos/* files."""
    todos_dir = base / ".claude" / "todos"
    items: list[TodoItem] = []
    if not todos_dir.is_dir():
        return items

    for file in sorted(todos_dir.iterdir()):
        if not file.is_file():
            continue
        try:
            text = file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                items.append(TodoItem(text=line, origin="agent", status="pending"))

    return items


def _scan_inline(root: str, recently_modified: list[str]) -> list[TodoItem]:
    """Scan recently modified source files for inline TODO/FIXME comments."""
    items: list[TodoItem] = []
    seen: set[str] = set()

    for rel_path in recently_modified:
        ext = os.path.splitext(rel_path)[1].lower()
        if ext not in _SCAN_EXTENSIONS:
            continue
        abs_path = os.path.join(root, rel_path)
        try:
            text = Path(abs_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line in text.splitlines():
            m = _TODO_RE.search(line)
            if m:
                content = m.group(1).strip()
                if content and content not in seen:
                    seen.add(content)
                    items.append(TodoItem(text=content, origin="comment", status="pending"))

    return items


def capture_todos(
    cwd: str | None = None,
    recently_modified: list[str] | None = None,
) -> list[TodoItem]:
    """Capture TODO items from all sources for the workspace at *cwd*.

    *recently_modified* is an optional list of relative paths to source files
    to scan for inline TODO comments (e.g. from capture_files output).
    """
    root = Path(cwd or os.getcwd())
    items: list[TodoItem] = []

    # 1. TODO.md
    todo_md = root / "TODO.md"
    if todo_md.exists():
        items.extend(_parse_todo_md(todo_md))

    # 2. .claude/todos/*
    items.extend(_parse_claude_todos(root))

    # 3. Inline comments
    if recently_modified:
        items.extend(_scan_inline(str(root), recently_modified))

    return items
