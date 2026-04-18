"""Claude Code hook installer — §11.7 of design doc.

Installs opt-in PreCompact and SessionEnd hooks into Claude Code's
settings (.claude/settings.json or ~/.claude/settings.json).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_CMD_PRE_COMPACT = "sessionmark save --auto --tag pre-compact --quiet --source claude-code"
_CMD_SESSION_END = "sessionmark save --auto --tag session-end --quiet --source claude-code"

_HOOK_ENTRIES = {
    "PreCompact": [
        {
            "matcher": "",
            "hooks": [{"type": "command", "command": _CMD_PRE_COMPACT}],
        }
    ],
    "SessionEnd": [
        {
            "matcher": "",
            "hooks": [{"type": "command", "command": _CMD_SESSION_END}],
        }
    ],
}


def install_hooks(
    cwd: str | None = None,
    dry_run: bool = False,
    global_scope: bool = False,
) -> dict:
    """Install PreCompact + SessionEnd hooks into Claude Code settings.

    Returns {"action": "installed"|"already_installed"|"dry_run", "path": str}

    If global_scope is True, writes to ~/.claude/settings.json.
    Otherwise writes to <cwd>/.claude/settings.json (project-local).
    """
    if global_scope:
        settings_path = Path.home() / ".claude" / "settings.json"
    else:
        base = Path(cwd) if cwd else Path(os.getcwd())
        settings_path = base / ".claude" / "settings.json"

    if dry_run:
        return {"action": "dry_run", "path": str(settings_path)}

    # Load or initialize settings
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
        settings_path.parent.mkdir(parents=True, exist_ok=True)

    hooks_section = data.setdefault("hooks", {})

    # Check if already installed (check both hook types)
    already = True
    for event, entries in _HOOK_ENTRIES.items():
        existing = hooks_section.get(event, [])
        for entry in entries:
            cmd = entry["hooks"][0]["command"]
            found = any(
                any(h.get("command") == cmd for h in e.get("hooks", []))
                for e in existing
            )
            if not found:
                already = False
                break

    if already:
        return {"action": "already_installed", "path": str(settings_path)}

    # Merge hook entries
    for event, entries in _HOOK_ENTRIES.items():
        existing = hooks_section.setdefault(event, [])
        for entry in entries:
            cmd = entry["hooks"][0]["command"]
            found = any(
                any(h.get("command") == cmd for h in e.get("hooks", []))
                for e in existing
            )
            if not found:
                existing.append(entry)

    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"action": "installed", "path": str(settings_path)}
