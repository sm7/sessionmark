"""MCP server tests — verifies tools load and respond correctly."""
import json


def test_mcp_server_importable():
    """MCP server module imports without error."""
    from bookmark.mcp import server
    assert hasattr(server, "app")


def test_mcp_bookmark_list_tool_exists():
    """bookmark_list tool is registered."""
    from bookmark.mcp.server import TOOL_NAMES
    assert "bookmark_list" in TOOL_NAMES


def test_mcp_bookmark_save_tool_exists():
    from bookmark.mcp.server import TOOL_NAMES
    assert "bookmark_save" in TOOL_NAMES


def test_mcp_bookmark_resume_tool_exists():
    from bookmark.mcp.server import TOOL_NAMES
    assert "bookmark_resume" in TOOL_NAMES


def test_mcp_list_returns_json(tmp_path, monkeypatch):
    """bookmark_list returns valid JSON list."""
    import asyncio
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    config = load_config()

    async def _call():
        from bookmark.mcp.server import handle_call_tool
        return await handle_call_tool("bookmark_list", {}, config=config)

    result = asyncio.run(_call())
    assert isinstance(result, list)
    # Parse first content item as JSON
    content = result[0].text if result else "[]"
    data = json.loads(content)
    assert isinstance(data, list)
