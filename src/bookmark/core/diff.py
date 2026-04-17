"""Diff between two bookmarks for bookmark-cli — §19 Week 5.

Compares two bookmarks and shows what changed: goal, files, todos, git state.
"""

from __future__ import annotations

from typing import Optional

from bookmark.config import Config


def diff_bookmarks(
    name1: str,
    name2: Optional[str] = None,
    config: Optional[Config] = None,
) -> None:
    """Compare two bookmarks, or one bookmark against current state.

    Parameters
    ----------
    name1:
        First bookmark name.
    name2:
        Second bookmark name. If None, compares against current workspace state.
    config:
        Pre-loaded Config object (loads fresh if None).
    """
    import json
    import sys

    import typer
    from rich.console import Console

    from bookmark.config import load_config
    from bookmark.core.resume import _load_config_and_conn, _load_open_files, _resolve_or_exit
    from bookmark.storage.db import get_todos

    if config is None:
        config = load_config()

    console = Console()

    cfg, conn = _load_config_and_conn(config)

    # Load first bookmark
    try:
        bm1 = _resolve_or_exit(conn, name1)
    except SystemExit as exc:
        conn.close()
        raise
    except Exception as exc:
        conn.close()
        raise ValueError(f"Could not load bookmark '{name1}': {exc}") from exc

    todos1 = get_todos(conn, bm1.id)
    files1 = _load_open_files(cfg, bm1)

    if name2 is not None:
        # Load second bookmark
        try:
            bm2 = _resolve_or_exit(conn, name2)
        except SystemExit:
            conn.close()
            raise
        except Exception as exc:
            conn.close()
            raise ValueError(f"Could not load bookmark '{name2}': {exc}") from exc

        todos2 = get_todos(conn, bm2.id)
        files2 = _load_open_files(cfg, bm2)
        label2 = name2
    else:
        # Compare against current workspace state
        from bookmark.capture.files import capture_files
        from bookmark.capture.git import capture_git
        from bookmark.capture.todos import capture_todos

        git2 = capture_git()
        raw_files2 = capture_files()
        todos_raw2 = capture_todos(recently_modified=[f.path for f in raw_files2])

        # Build a pseudo-bm2 for comparison
        from bookmark.core.models import Bookmark
        bm2 = Bookmark(
            id="current",
            name="current",
            slug="current",
            created_at=0,
            repo_root=git2.repo_root or "",
            git_branch=git2.branch,
            git_head=git2.head,
            goal="(current workspace)",
        )
        todos2 = todos_raw2
        files2 = raw_files2
        label2 = "current"

    conn.close()

    # -------------------------------------------------------------------
    # Render diff output using rich
    # -------------------------------------------------------------------
    console.print(f"\n[bold]DIFF: {name1} → {label2}[/bold]\n")

    # GOAL
    console.print("[bold underline]GOAL[/bold underline]")
    goal1 = bm1.goal or ""
    goal2 = bm2.goal or ""
    if goal1 != goal2:
        if goal1:
            console.print(f"  [red]- {goal1}[/red]")
        if goal2:
            console.print(f"  [green]+ {goal2}[/green]")
    else:
        console.print(f"  (unchanged) {goal1 or '(none)'}")
    console.print()

    # FILES
    console.print("[bold underline]FILES[/bold underline]")
    paths1 = {f.path for f in files1}
    paths2 = {f.path for f in files2}

    added = paths2 - paths1
    removed = paths1 - paths2
    same = paths1 & paths2

    for p in sorted(added):
        console.print(f"  [green]+ {p}[/green]  [dim](added)[/dim]")
    for p in sorted(removed):
        console.print(f"  [red]- {p}[/red]  [dim](removed)[/dim]")
    for p in sorted(same):
        f1 = next((f for f in files1 if f.path == p), None)
        f2 = next((f for f in files2 if f.path == p), None)
        if f1 and f2 and (f1.additions != f2.additions or f1.deletions != f2.deletions):
            console.print(f"  [yellow]~ {p}[/yellow]  [dim](modified)[/dim]")

    if not added and not removed and not any(
        (f1.additions != f2.additions or f1.deletions != f2.deletions)
        for p in same
        for f1 in [next((f for f in files1 if f.path == p), None)]
        for f2 in [next((f for f in files2 if f.path == p), None)]
        if f1 and f2
    ):
        console.print("  (no file changes)")
    console.print()

    # TODOS
    console.print("[bold underline]TODOS[/bold underline]")
    texts1 = {t.text for t in todos1}
    texts2 = {t.text for t in todos2}

    todo_added = texts2 - texts1
    todo_removed = texts1 - texts2

    for t in sorted(todo_added):
        console.print(f"  [green]+ [ ] {t}[/green]")
    for t in sorted(todo_removed):
        # Check if it was completed
        t_obj = next((x for x in todos1 if x.text == t), None)
        if t_obj and t_obj.status == "done":
            console.print(f"  [dim]- [x] {t}[/dim]")
        else:
            console.print(f"  [red]- [ ] {t}[/red]")

    if not todo_added and not todo_removed:
        console.print("  (no todo changes)")
    console.print()

    # GIT
    console.print("[bold underline]GIT[/bold underline]")
    branch1 = bm1.git_branch or "(none)"
    branch2 = bm2.git_branch or "(none)"
    head1 = (bm1.git_head or "")[:7] or "(none)"
    head2 = (bm2.git_head or "")[:7] or "(none)"

    if branch1 != branch2:
        console.print(f"  branch: {branch1} → {branch2}")
    else:
        console.print(f"  branch: {branch1} (unchanged)")

    if head1 != head2:
        console.print(f"  head:   {head1} → {head2}")
    else:
        console.print(f"  head:   {head1} (unchanged)")
    console.print()
