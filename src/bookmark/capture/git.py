"""Git context capture for bookmark-cli.

Uses subprocess to run git commands in the current working directory.
Captures:
- Current branch name
- HEAD SHA
- Short diff summary (files changed, insertions, deletions)
- List of modified/untracked files with their status letter

Fails gracefully if not in a git repo.

See design doc §5 for capture pipeline overview.
"""

from __future__ import annotations

import subprocess
from typing import Optional

from bookmark.core.models import FileEntry, GitInfo


def _run(args: list[str], cwd: Optional[str] = None) -> str:
    """Run a git command and return stdout. Returns '' on any error."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return ""


def capture_git(cwd: Optional[str] = None) -> GitInfo:
    """Capture git context for the repo at *cwd* (default: process cwd).

    Returns a GitInfo with all available fields populated.
    Fields that cannot be determined are left as None/0.
    """
    # ---- repo root ----
    repo_root = _run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if not repo_root:
        return GitInfo()

    effective_cwd = repo_root  # run remaining commands at repo root

    # ---- repo name (last path component) ----
    repo_name = repo_root.split("/")[-1] if repo_root else None

    # ---- branch ----
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=effective_cwd)
    if branch == "HEAD":
        branch = None  # detached HEAD

    # ---- HEAD sha ----
    head = _run(["git", "rev-parse", "HEAD"], cwd=effective_cwd)
    if not head:
        head = None

    # ---- diff stat against HEAD ----
    files_changed = 0
    insertions = 0
    deletions = 0
    stat_out = _run(
        ["git", "diff", "--stat", "HEAD", "--", "."],
        cwd=effective_cwd,
    )
    if stat_out:
        # Last line looks like: " 3 files changed, 42 insertions(+), 5 deletions(-)"
        for line in stat_out.splitlines():
            if "changed" in line:
                for token in line.split(","):
                    token = token.strip()
                    if "changed" in token:
                        try:
                            files_changed = int(token.split()[0])
                        except ValueError:
                            pass
                    elif "insertion" in token:
                        try:
                            insertions = int(token.split()[0])
                        except ValueError:
                            pass
                    elif "deletion" in token:
                        try:
                            deletions = int(token.split()[0])
                        except ValueError:
                            pass

    # ---- modified / staged files ----
    status_out = _run(
        ["git", "status", "--porcelain"],
        cwd=effective_cwd,
    )
    modified_files: list[FileEntry] = []
    if status_out:
        for line in status_out.splitlines():
            if len(line) < 3:
                continue
            xy = line[:2].strip() or "?"
            path = line[3:].strip()
            # For renames "old -> new" git shows "R old -> new"
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            modified_files.append(FileEntry(path=path, status=xy))

    return GitInfo(
        branch=branch,
        head=head,
        repo_root=repo_root,
        repo_name=repo_name,
        files_changed=files_changed,
        insertions=insertions,
        deletions=deletions,
        modified_files=modified_files,
    )
