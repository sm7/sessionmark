"""Per-agent config file installer.

Installs sessionmark context sections into project-local agent config files.
Each agent reads its own config file at startup, giving it automatic session
context without any trigger phrase.

Idempotent: if the section is already present, returns "already_installed".
"""

from __future__ import annotations

import os
from pathlib import Path

from bookmark.install.context_writer import CONFIG_FILES, has_section, install_section

# Agents supported (matches Section 5 of design doc — aider excluded, no auto-loaded file)
AGENTS = ["claude-code", "codex", "cursor", "github-copilot", "windsurf", "gemini"]


def install_for_agent(
    agent: str,
    cwd: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Install sessionmark section for the given agent's config file.

    Returns dict with keys agent, dest, action.
    Action is one of: "installed", "already_installed", "dry_run".
    """
    if agent not in CONFIG_FILES:
        raise ValueError(f"Unknown agent '{agent}'. Supported: {', '.join(AGENTS)}")

    cfg = CONFIG_FILES[agent]
    base = Path(cwd) if cwd else Path(os.getcwd())
    dest_path = base / cfg["path"]

    if dry_run:
        return {"agent": agent, "dest": str(dest_path), "action": "dry_run"}

    action = install_section(dest_path, mode=cfg["mode"])  # type: ignore[arg-type]
    return {"agent": agent, "dest": str(dest_path), "action": action}


def install_for_all(
    cwd: str | None = None,
    dry_run: bool = False,
) -> list[dict]:
    """Install sessionmark sections for all supported agents.

    Returns a list of result dicts (one per agent).
    """
    results = []
    for agent in AGENTS:
        try:
            result = install_for_agent(agent, cwd=cwd, dry_run=dry_run)
        except Exception as exc:
            base = Path(cwd) if cwd else Path(os.getcwd())
            dest = str(base / CONFIG_FILES.get(agent, {}).get("path", ""))
            result = {"agent": agent, "dest": dest, "action": "skipped", "error": str(exc)}
        results.append(result)
    return results


def list_installs(cwd: str | None = None) -> list[dict]:
    """Show which agents have sessionmark sections installed.

    Returns list of dicts: {"agent": ..., "dest": ..., "installed": bool}
    """
    base = Path(cwd) if cwd else Path(os.getcwd())
    results = []
    for agent in AGENTS:
        cfg = CONFIG_FILES[agent]
        dest_path = base / cfg["path"]
        results.append({
            "agent": agent,
            "dest": str(dest_path),
            "installed": has_section(dest_path),
        })
    return results
