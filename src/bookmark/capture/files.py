"""Recently-modified file capture for bookmark-cli.

Walks the current working directory and finds files modified in the last
2 hours. Respects .gitignore for untracked files by delegating to
`git ls-files --others --exclude-standard`.

Returns a list of FileEntry objects.

See design doc §5 for capture pipeline overview.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from bookmark.core.models import FileEntry

_TWO_HOURS = 2 * 60 * 60  # seconds

# Directories to always skip
_SKIP_DIRS = frozenset(
    {".git", "__pycache__", ".mypy_cache", ".ruff_cache", "node_modules", ".venv", "venv"}
)


def _get_untracked(cwd: str) -> set[str]:
    """Return set of untracked paths that are not gitignored."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=10,
        )
        if result.returncode == 0:
            return {line.strip() for line in result.stdout.splitlines() if line.strip()}
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return set()


def _get_numstat(cwd: str) -> dict[str, tuple[int, int]]:
    """Return {relative_path: (additions, deletions)} from git diff --numstat HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", "--numstat", "HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=10,
        )
        if result.returncode != 0:
            return {}
        stats: dict[str, tuple[int, int]] = {}
        for line in result.stdout.splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            add_s, del_s, path = parts
            try:
                stats[path.strip()] = (int(add_s), int(del_s))
            except ValueError:
                # Binary files show "-" — leave as 0
                stats[path.strip()] = (0, 0)
        return stats
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return {}


def capture_files(cwd: Optional[str] = None, max_age_seconds: int = _TWO_HOURS) -> list[FileEntry]:
    """Return recently modified files under *cwd*.

    Files modified within *max_age_seconds* seconds ago are included.
    .gitignored untracked files are excluded.
    """
    root = cwd or os.getcwd()
    now = time.time()
    cutoff = now - max_age_seconds

    untracked = _get_untracked(root)
    numstat = _get_numstat(root)

    entries: list[FileEntry] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place so os.walk doesn't recurse into them
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

        for filename in filenames:
            abs_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(abs_path, root)

            try:
                mtime = os.path.getmtime(abs_path)
            except OSError:
                continue

            if mtime < cutoff:
                continue

            # Determine status
            if rel_path in untracked:
                status = "?"
            else:
                status = "M"

            # Per-file diff stats from git (0,0 for untracked / binary)
            additions, deletions = numstat.get(rel_path, (0, 0))

            entries.append(FileEntry(
                path=rel_path,
                status=status,
                additions=additions,
                deletions=deletions,
            ))

    return entries
