"""Doctor health check orchestration — bookmark doctor command."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Optional

from bookmark.config import Config


def run_doctor(config: Optional[Config] = None) -> None:
    """Run all health checks and print results."""
    if config is None:
        from bookmark.config import load_config
        config = load_config()

    home = config.home

    # Use print() so capsys can capture it
    _hline = "─" * 44

    print("bookmark doctor")
    print(_hline)

    # 1. Bookmark home exists and is writable
    if home.exists() and home.is_dir():
        try:
            test_file = home / ".bookmark_doctor_write_test"
            test_file.touch()
            test_file.unlink()
            print(f"✓ bookmark home       {home}/")
        except OSError:
            print(f"✗ bookmark home       {home}/ (not writable)")
    else:
        print(f"✗ bookmark home       {home}/ (does not exist)")

    # 2. SQLite DB check
    db_path = home / "bookmarks.db"
    if db_path.exists():
        try:
            import sqlite3
            from bookmark.storage.db import SCHEMA_VERSION, open_db
            conn = open_db(db_path)
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            count = conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
            conn.close()
            if version == SCHEMA_VERSION:
                print(f"✓ SQLite DB           schema v{version}, {count} bookmark(s)")
            else:
                print(f"! SQLite DB           schema v{version} (expected v{SCHEMA_VERSION})")
        except Exception as exc:
            print(f"✗ SQLite DB           error: {exc}")
    else:
        print(f"- SQLite DB           not found (will be created on first save)")

    # 3. Blob store
    blob_dir = home / "blobs"
    if blob_dir.exists():
        blob_count = sum(1 for _ in blob_dir.rglob("*") if _.is_file())
        print(f"✓ blob store          {blob_dir}/ ({blob_count} blob(s))")
    else:
        print(f"- blob store          {blob_dir}/ (not yet created)")

    # 4. MCP server — check if bookmark-mcp entry point is importable/installed
    mcp_installed = shutil.which("bookmark-mcp") is not None
    if not mcp_installed:
        # Also try importability
        try:
            import bookmark.mcp.server  # noqa: F401
            mcp_installed = True
        except ImportError:
            pass

    if mcp_installed:
        print(f"✓ MCP server          bookmark-mcp installed")
    else:
        print(f"- MCP server          bookmark-mcp not found in PATH")

    # 5. Configured briefing provider
    provider = config.briefing_provider
    if provider == "template":
        print(f"- briefing provider   template (no LLM)")
    else:
        print(f"✓ briefing provider   {provider}")

    # 6. Per-agent paths (informational)
    _check_agent_path("claude-code", Path.home() / ".claude" / "projects")
    _check_agent_path("cursor", Path.home() / ".cursor" / "User" / "workspaceStorage")
    _check_agent_path("codex", Path.home() / ".codex" / "sessions")
    _check_agent_path("gemini", Path.home() / ".gemini" / "sessions")
    print(f"  aider               per-repo only (.aider.chat.history.md)")

    # 7. Sync status
    if config.sync_enabled:
        sync_dir = home / "sync"
        if (sync_dir / ".git").exists():
            remote = config.git_remote or "(no remote configured)"
            print(f"✓ sync                enabled, sync dir initialized ({remote})")
        else:
            print(f"! sync                enabled but sync dir not initialized — run 'bookmark sync init'")
    else:
        print(f"- sync                disabled")

    print(_hline)


def _check_agent_path(agent: str, path: Path) -> None:
    """Check if an agent's session path exists and print status."""
    if path.exists():
        print(f"✓ {agent:<20} {path} found")
    else:
        print(f"  {agent:<20} {path} not found")
