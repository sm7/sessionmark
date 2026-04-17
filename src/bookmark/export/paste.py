"""Paste-format export for bookmark-cli — §11.5 of design doc.

Renders bookmark context as a paste-ready Markdown block for the target agent.
Uses Jinja2 templates from src/bookmark/export/templates/.
"""

from __future__ import annotations

from typing import Optional

VALID_TARGETS = {"generic", "claude", "cursor", "codex", "gemini", "aider"}


def render_paste(
    bookmark,
    todos,
    transcript,
    open_files,
    target: str = "generic",
    config=None,
) -> str:
    """Render a paste-format export for the given target agent.

    Parameters
    ----------
    bookmark:
        Bookmark model instance.
    todos:
        List of TodoItem instances.
    transcript:
        List of message dicts (role + content).
    open_files:
        List of FileEntry instances.
    target:
        Target agent name. Falls back to "generic" if unknown.
    config:
        Unused; reserved for future use.
    """
    from jinja2 import Environment, PackageLoader, select_autoescape

    env = Environment(
        loader=PackageLoader("bookmark", "export/templates"),
        autoescape=select_autoescape([]),
    )
    template_name = f"{target}.md.j2" if target in VALID_TARGETS else "generic.md.j2"
    template = env.get_template(template_name)
    pending_todos = [t for t in todos if t.status == "pending"]
    return template.render(
        bookmark=bookmark,
        todos=todos,
        pending_todos=pending_todos,
        transcript=transcript,
        open_files=open_files,
    )
