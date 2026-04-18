"""Per-agent skill/command file installer — §11.4 of design doc.

Installs skill files for coding agents into the current project directory.
Idempotent: if the file already exists with identical content, returns "already_installed".
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Agents supported
AGENTS = ["claude-code", "cursor", "codex", "gemini", "aider", "github-copilot"]

# Map agent -> (relative destination path, source skill file relative to package skills/)
_AGENT_CONFIG = {
    "claude-code": {
        "dest": ".claude/skills/bookmark/SKILL.md",
        "source": "claude_code/SKILL.md",
        "append": False,
        "append_marker": None,
    },
    "cursor": {
        "dest": ".cursor/rules/bookmark.mdc",
        "source": "cursor/bookmark.mdc",
        "append": False,
        "append_marker": None,
    },
    "codex": {
        "dest": ".codex/commands/bookmark.md",
        "source": "codex/bookmark.md",
        "append": False,
        "append_marker": None,
    },
    "gemini": {
        "dest": ".gemini/commands/bookmark.md",
        "source": "gemini/bookmark.md",
        "append": False,
        "append_marker": None,
    },
    "aider": {
        "dest": "CONVENTIONS.md",
        "source": "aider/CONVENTIONS.md",
        "append": True,
        "append_marker": "## Bookmark",
    },
    "github-copilot": {
        "dest": ".github/copilot-instructions.md",
        "source": "github_copilot/bookmark.md",
        "append": True,
        "append_marker": "## Bookmark",
    },
}


def _skills_dir() -> Path:
    """Return the path to the package skills/ directory."""
    return Path(__file__).parent.parent / "skills"


def _read_source(agent: str) -> str:
    """Read the skill template content for the given agent."""
    source_rel = _AGENT_CONFIG[agent]["source"]
    source_path = _skills_dir() / source_rel
    return source_path.read_text(encoding="utf-8")


def install_for_agent(
    agent: str,
    cwd: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Install skill file for the given agent.

    Returns {"agent": ..., "dest": ..., "action": "installed"|"already_installed"|"skipped"|"dry_run"}
    Idempotent: if file already exists with same content, returns "already_installed".
    """
    if agent not in _AGENT_CONFIG:
        raise ValueError(f"Unknown agent '{agent}'. Supported: {', '.join(AGENTS)}")

    cfg = _AGENT_CONFIG[agent]
    base = Path(cwd) if cwd else Path(os.getcwd())
    dest_path = base / cfg["dest"]
    source_content = _read_source(agent)

    if dry_run:
        return {"agent": agent, "dest": str(dest_path), "action": "dry_run"}

    # Aider: append mode — check for marker in existing file
    if cfg["append"]:
        marker = cfg["append_marker"]
        if dest_path.exists():
            existing = dest_path.read_text(encoding="utf-8")
            if marker and marker in existing:
                return {"agent": agent, "dest": str(dest_path), "action": "already_installed"}
            # Append the section
            new_content = existing.rstrip("\n") + "\n\n" + source_content
            dest_path.write_text(new_content, encoding="utf-8")
            return {"agent": agent, "dest": str(dest_path), "action": "installed"}
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text(source_content, encoding="utf-8")
            return {"agent": agent, "dest": str(dest_path), "action": "installed"}

    # Normal mode: write full file
    if dest_path.exists():
        existing = dest_path.read_text(encoding="utf-8")
        if existing == source_content:
            return {"agent": agent, "dest": str(dest_path), "action": "already_installed"}
        # Content differs — overwrite
        dest_path.write_text(source_content, encoding="utf-8")
        return {"agent": agent, "dest": str(dest_path), "action": "updated"}

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(source_content, encoding="utf-8")
    return {"agent": agent, "dest": str(dest_path), "action": "installed"}


def install_for_all(
    cwd: Optional[str] = None,
    dry_run: bool = False,
) -> list[dict]:
    """Install skill files for all supported agents.

    Returns a list of result dicts (one per agent).
    """
    results = []
    for agent in AGENTS:
        try:
            result = install_for_agent(agent, cwd=cwd, dry_run=dry_run)
        except Exception as exc:
            result = {"agent": agent, "dest": "", "action": "skipped", "error": str(exc)}
        results.append(result)
    return results


def list_installs(cwd: Optional[str] = None) -> list[dict]:
    """Show which agents have skills installed.

    Returns a list of dicts: {"agent": ..., "dest": ..., "installed": bool}
    """
    base = Path(cwd) if cwd else Path(os.getcwd())
    results = []
    for agent, cfg in _AGENT_CONFIG.items():
        dest_path = base / cfg["dest"]
        installed = False
        if dest_path.exists():
            if cfg["append"]:
                marker = cfg["append_marker"]
                content = dest_path.read_text(encoding="utf-8")
                installed = marker is not None and marker in content
            else:
                installed = True
        results.append({"agent": agent, "dest": str(dest_path), "installed": installed})
    return results
