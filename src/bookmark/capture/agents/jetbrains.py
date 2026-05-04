"""JetBrains GitHub Copilot Chat fallback session reader — §11.7 of design doc.

JetBrains stores plugin state as XML in per-product config directories:
  Linux:   ~/.config/JetBrains/<Product><Version>/options/
  macOS:   ~/Library/Application Support/JetBrains/<Product><Version>/options/
  Windows: %APPDATA%/JetBrains/<Product><Version>/options/

The GitHub Copilot plugin serialises chat history as JSON inside XML option
values. We search across all installed products and try known filenames,
picking the most recently modified one.

Note: the skill/instructions file (.github/copilot-instructions.md) is shared
with the github-copilot installer entry — install via:
  sessionmark install --for github-copilot
"""

from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Filenames the Copilot plugin may use for its persisted state.
_COPILOT_XML_NAMES = [
    "github.copilot.xml",
    "GitHubCopilot.xml",
    "github-copilot.xml",
    "copilot.xml",
]


def _jetbrains_root(_base_dir: Path | None = None) -> Path:
    home = _base_dir if _base_dir is not None else Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "JetBrains"
    if sys.platform == "win32":
        base = _base_dir or Path(os.environ.get("APPDATA", ""))
        return base / "JetBrains"
    return home / ".config" / "JetBrains"


def _candidate_xml_files(root: Path) -> list[Path]:
    """Return Copilot XML files across all JetBrains products, newest first."""
    if not root.exists():
        return []
    found = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        options = entry / "options"
        if not options.is_dir():
            continue
        for name in _COPILOT_XML_NAMES:
            xml_path = options / name
            if xml_path.exists():
                found.append(xml_path)
    found.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return found


def _messages_from_xml(path: Path, n: int | None) -> list[dict]:
    """Best-effort extraction of chat messages from a JetBrains XML state file.

    The Copilot plugin stores chat as JSON-encoded strings inside XML option
    element attributes or text nodes — we scan all of them.
    """
    try:
        tree = ET.parse(str(path))
    except ET.ParseError:
        return []

    candidates: list[list[dict]] = []

    for elem in tree.iter():
        # Check attribute values
        for val in elem.attrib.values():
            msgs = _try_parse_json_messages(val, n)
            if msgs:
                candidates.append(msgs)
        # Check element text
        text = (elem.text or "").strip()
        if text:
            msgs = _try_parse_json_messages(text, n)
            if msgs:
                candidates.append(msgs)

    if not candidates:
        return []
    # Return the candidate with the most messages (most likely the real history)
    return max(candidates, key=len)


def _try_parse_json_messages(raw: str, n: int | None) -> list[dict]:
    if not raw or raw[0] not in ("[", "{"):
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return _extract_messages(data, n)


def _extract_messages(data: object, n: int | None) -> list[dict]:
    if isinstance(data, dict):
        # Try common wrapper keys
        for key in ("conversations", "history", "messages", "chat"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            return []
    if not isinstance(data, list):
        return []
    messages: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        role = item.get("role") or item.get("type", "")
        content = item.get("content") or item.get("text") or item.get("message", "")
        if role and content and isinstance(content, str):
            role = "user" if role in ("user", "human") else "assistant"
            messages.append({"role": role, "content": content})
    return messages if n is None else messages[-n:]


def read_recent_transcript(
    cwd: str,
    n_messages: int | None = None,
    _base_dir: Path | None = None,
) -> list[dict]:
    """Best-effort read of most recent JetBrains Copilot Chat session."""
    root = _jetbrains_root(_base_dir)
    for xml_path in _candidate_xml_files(root):
        msgs = _messages_from_xml(xml_path, n_messages)
        if msgs:
            return msgs
    return []
