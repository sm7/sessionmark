"""Runtime environment capture for bookmark-cli.

Collects environment metadata from the current workspace:
- Python version (sys.version_info)
- Node.js version (subprocess `node --version`)
- Active virtualenv name ($VIRTUAL_ENV)
- pyproject.toml project name (tomllib)
- package.json name (json.load)

Each item fails silently so a missing tool never aborts the save.

See design doc §5 for capture pipeline overview.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from bookmark.core.models import EnvVar


def _run_version(cmd: list[str]) -> str | None:
    """Run a command and return its trimmed stdout, or None on any failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def capture_env(cwd: str | None = None) -> list[EnvVar]:
    """Return a list of EnvVar items describing the current runtime environment."""
    root = Path(cwd or os.getcwd())
    items: list[EnvVar] = []

    # Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    items.append(EnvVar(key="python_version", value=py_ver))

    # Node.js version
    node_ver = _run_version(["node", "--version"])
    if node_ver:
        items.append(EnvVar(key="node_version", value=node_ver))

    # Active virtualenv
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        items.append(EnvVar(key="venv", value=Path(venv).name))

    # pyproject.toml project name
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            with pyproject.open("rb") as fh:
                data = tomllib.load(fh)
            name = data.get("project", {}).get("name") or data.get("tool", {}).get(
                "poetry", {}
            ).get("name")
            if name:
                items.append(EnvVar(key="pyproject_name", value=name))
        except Exception:  # noqa: BLE001
            pass

    # package.json name
    pkg_json = root / "package.json"
    if pkg_json.is_file():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            name = data.get("name")
            if name:
                items.append(EnvVar(key="package_json_name", value=name))
        except Exception:  # noqa: BLE001
            pass

    return items
