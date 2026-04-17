"""Shell history capture for bookmark-cli.

Reads the last 20 commands from the user's shell history file.
Supports:
- zsh EXTENDED_HISTORY format: `: <timestamp>:<elapsed>;<cmd>`
- bash plain format (one command per line in ~/.bash_history)

Skips gracefully if the shell or history file is unknown/unreadable.

See design doc §5 for capture pipeline overview.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

_ZSH_ENTRY = re.compile(r"^:\s*\d+:\d+;(.+)$")

_N = 20  # number of commands to capture


def _read_zsh(path: Path) -> list[str]:
    """Parse zsh EXTENDED_HISTORY file, returning last *_N* commands."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    commands: list[str] = []
    for line in lines:
        m = _ZSH_ENTRY.match(line)
        if m:
            commands.append(m.group(1).strip())
        elif line and not line.startswith(":"):
            # Plain zsh history (no EXTENDED_HISTORY option)
            commands.append(line.strip())

    return commands[-_N:]


def _read_bash(path: Path) -> list[str]:
    """Parse plain bash history file."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    return [l.strip() for l in lines if l.strip()][-_N:]


def capture_shell_history(histfile: Optional[str] = None) -> list[str]:
    """Return the last *_N* shell commands from the history file.

    *histfile* overrides the auto-detected path (useful in tests).
    Returns an empty list if history cannot be read.
    """
    path_str = histfile or os.environ.get("HISTFILE", "")

    if path_str:
        path = Path(path_str).expanduser()
        if path.exists():
            # Detect format by path name heuristic
            if "zsh" in path.name or path.name == ".zsh_history":
                return _read_zsh(path)
            return _read_bash(path)

    # Fallbacks: try common locations
    home = Path.home()
    for candidate, reader in [
        (home / ".zsh_history", _read_zsh),
        (home / ".bash_history", _read_bash),
    ]:
        if candidate.exists():
            result = reader(candidate)
            if result:
                return result

    return []
