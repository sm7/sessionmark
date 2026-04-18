"""MCP server for bookmark-cli — §12 of design doc.

Exposes bookmark operations as MCP tools over stdio.

Tools:
- bookmark_save(name, message, tags) -> {id, name, summary}
- bookmark_resume(name) -> {briefing, goal, open_files, todos, next_step, source, saved_at}
- bookmark_list(repo, tag, limit) -> [{name, when, goal}]
- bookmark_search(query, limit) -> [{name, snippet, score}]
- bookmark_show(name) -> full bookmark record as dict
"""

from __future__ import annotations

import json
import time

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("bookmark")

# Tool names registry — used by tests to verify registration
TOOL_NAMES = {
    "bookmark_save",
    "bookmark_resume",
    "bookmark_list",
    "bookmark_search",
    "bookmark_show",
}


def _relative_time(ts: int) -> str:
    diff = int(time.time()) - ts
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of MCP tools exposed by bookmark-cli."""
    return [
        Tool(
            name="bookmark_save",
            description="Save the current workspace as a bookmark.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "default": "wip", "description": "Bookmark name."},
                    "message": {"type": "string", "default": "", "description": "One-line goal."},
                    "tags": {
                        "type": "string", "default": "", "description": "Comma-separated tags."
                    },
                },
            },
        ),
        Tool(
            name="bookmark_resume",
            description="Resume a saved bookmark — returns briefing and context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "default": "latest",
                        "description": "Bookmark name or 'latest'.",
                    },
                },
            },
        ),
        Tool(
            name="bookmark_list",
            description="List saved bookmarks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string", "default": "", "description": "Filter by repo name."
                    },
                    "tag": {"type": "string", "default": "", "description": "Filter by tag."},
                    "limit": {"type": "integer", "default": 10, "description": "Max results."},
                },
            },
        ),
        Tool(
            name="bookmark_search",
            description="Full-text search over bookmark names, goals, and tags.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms."},
                    "limit": {"type": "integer", "default": 10, "description": "Max results."},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="bookmark_show",
            description="Show full details of a bookmark.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Bookmark name or 'latest'."},
                },
                "required": ["name"],
            },
        ),
    ]


async def handle_call_tool(
    name: str,
    arguments: dict,
    config=None,
) -> list[TextContent]:
    """Dispatch tool call to the appropriate handler.

    Separated from the decorator so tests can call it directly.
    """
    if config is None:
        from bookmark.config import load_config
        config = load_config()

    from bookmark.storage.db import get_todos, list_bookmarks, open_db, resolve_name

    db_path = config.home / "bookmarks.db"
    conn = open_db(db_path)

    try:
        if name == "bookmark_list":
            repo = arguments.get("repo") or None
            tag = arguments.get("tag") or None
            limit = int(arguments.get("limit", 10))
            bms = list_bookmarks(conn, repo=repo, tag=tag, n=limit)
            result = [
                {"name": bm.name, "when": _relative_time(bm.created_at), "goal": bm.goal}
                for bm in bms
            ]
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "bookmark_save":
            bm_name = arguments.get("name", "wip")
            message = arguments.get("message", "") or None
            tags = arguments.get("tags", "") or None
            from bookmark.core.save import save_bookmark
            bm = save_bookmark(name=bm_name, goal=message, tags=tags, config=config)
            result = {"id": bm.id, "name": bm.name, "summary": bm.goal or ""}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "bookmark_resume":
            bm_name = arguments.get("name", "latest")
            if bm_name == "latest":
                rows = list_bookmarks(conn, n=1)
                if not rows:
                    err = json.dumps({"error": "No bookmarks found."})
                    return [TextContent(type="text", text=err)]
                bm = rows[0]
            else:
                bm = resolve_name(conn, bm_name)
                if bm is None:
                    err = json.dumps({"error": f"Bookmark '{bm_name}' not found."})
                    return [TextContent(type="text", text=err)]

            todos = get_todos(conn, bm.id)

            from bookmark.core.resume import _load_open_files, _load_transcript
            transcript = _load_transcript(config, bm)
            open_files = _load_open_files(config, bm)

            from bookmark.briefing.template import render_briefing
            briefing = render_briefing(
                bookmark=bm,
                todos=todos,
                transcript=transcript,
                open_files=open_files,
                include_next_step=True,
            )

            result = {
                "briefing": briefing,
                "goal": bm.goal,
                "open_files": [{"path": f.path, "status": f.status} for f in open_files],
                "todos": [{"text": t.text, "status": t.status} for t in todos],
                "next_step": (
                    f"cd {bm.repo_root}"
                    + (f" && git checkout {bm.git_branch}" if bm.git_branch else "")
                ),
                "source": bm.source,
                "saved_at": bm.created_at,
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "bookmark_search":
            query = arguments.get("query", "")
            limit = int(arguments.get("limit", 10))
            from bookmark.storage.db import search_bookmarks
            pairs = search_bookmarks(conn, query, limit=limit)
            result = [
                {"name": bm.name, "snippet": snippet, "score": 0}
                for bm, snippet in pairs
            ]
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "bookmark_show":
            bm_name = arguments.get("name", "latest")
            if bm_name == "latest":
                rows = list_bookmarks(conn, n=1)
                if not rows:
                    err = json.dumps({"error": "No bookmarks found."})
                    return [TextContent(type="text", text=err)]
                bm = rows[0]
            else:
                bm = resolve_name(conn, bm_name)
                if bm is None:
                    err = json.dumps({"error": f"Bookmark '{bm_name}' not found."})
                    return [TextContent(type="text", text=err)]

            todos = get_todos(conn, bm.id)
            data = bm.model_dump()
            data["todos"] = [t.model_dump() for t in todos]
            return [TextContent(type="text", text=json.dumps(data, indent=2))]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    finally:
        conn.close()


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """MCP tool dispatcher — called by the MCP runtime."""
    return await handle_call_tool(name, arguments)


async def main() -> None:
    """Run the MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def run() -> None:
    """Entry point for bookmark-mcp."""
    import asyncio
    asyncio.run(main())
