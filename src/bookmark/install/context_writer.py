"""LPIC+CSV context injection into agent config files.

Writes compressed session context into project-local agent config files so any
agent opened in the directory automatically sees the last saved session.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

CONFIG_FILES: dict[str, dict] = {
    "claude-code": {"path": "CLAUDE.md", "mode": "append_section"},
    "codex": {"path": "AGENTS.md", "mode": "append_section"},
    "cursor": {"path": ".cursor/rules/sessionmark.mdc", "mode": "append_section"},
    "github-copilot": {"path": ".github/copilot-instructions.md", "mode": "append_section"},
    "windsurf": {"path": ".windsurf/rules/sessionmark.md", "mode": "append_section"},
    "gemini": {"path": ".gemini/system.md", "mode": "full_override"},
}

SCHEMA_LINE = (
    "<!-- sessionmark-schema: fields sep=, lists sep=| bool=0/1 "
    "keys:n=name,g=goal,b=branch,h=head,r=repo,s=source,f=files(type:path),"
    "t=todos(done:text),c=commands,x=context,nxt=next_step. "
    "When you see a sessionmark block expand all single-letter tokens "
    "using the dict before reading the session context. -->"
)

SECTION_RE = re.compile(
    r"<!-- sessionmark:start.*?<!-- sessionmark:end -->",
    re.DOTALL,
)


def build_dict(session_str: str) -> dict[str, str]:
    """Find repeated substrings and build LPIC substitution dictionary.

    Uses a greedy approach: assigns A to the best candidate, applies the
    substitution to the working string, then finds B in the modified string,
    etc. This prevents assigning keys to substrings that overlap with or are
    substrings of already-selected values.
    """
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result: dict[str, str] = {}
    working = session_str
    used_keys: set[str] = set()
    idx = 0

    for _ in range(26):
        if idx >= 26 or len(working) < 10:
            break

        # Skip key letters that already appear in the working string.
        # This ensures substitution tokens are unambiguous during decode.
        while idx < 26 and letters[idx] in working:
            idx += 1
        if idx >= 26:
            break

        # Count occurrences of all substrings (length 5-80) in working string.
        # Skip substrings that contain any already-used key letter.
        counts: dict[str, int] = {}
        w = len(working)
        for start in range(w):
            for end in range(start + 5, min(start + 80, w + 1)):
                sub = working[start:end]
                if any(k in sub for k in used_keys):
                    continue
                if sub not in counts:
                    counts[sub] = working.count(sub)

        # Pick the highest-scoring candidate
        best_sub = None
        best_score = 0
        for sub, cnt in counts.items():
            if cnt < 2:
                continue
            key = letters[idx]
            overhead = len(key) + 1 + len(sub) + 1
            net_saving = (cnt - 1) * len(sub)
            if net_saving > overhead and net_saving > best_score:
                best_score = net_saving
                best_sub = sub

        if best_sub is None:
            break

        key = letters[idx]
        result[key] = best_sub
        working = working.replace(best_sub, key)
        used_keys.add(key)
        idx += 1

    return result


def encode_session(session: dict, sub_dict: dict[str, str]) -> str:
    """Encode session fields as a single CSV line with dictionary substitutions applied."""
    f_str = "|".join(session.get("f") or [])
    t_str = "|".join(session.get("t") or [])
    c_str = "|".join(session.get("c") or [])

    fields = [
        ("n", session.get("n") or ""),
        ("g", session.get("g") or ""),
        ("b", session.get("b") or ""),
        ("h", session.get("h") or ""),
        ("r", session.get("r") or ""),
        ("s", session.get("s") or ""),
        ("f", f_str),
        ("t", t_str),
        ("c", c_str),
        ("x", session.get("x") or ""),
        ("nxt", session.get("nxt") or ""),
    ]

    csv_line = ",".join(f"{k}:{v}" for k, v in fields if v)

    # Apply substitutions longest-value-first to avoid partial matches
    for value in sorted(sub_dict.values(), key=len, reverse=True):
        key = next(k for k, v in sub_dict.items() if v == value)
        csv_line = csv_line.replace(value, key)

    return csv_line


def extract_transcript_context(transcript_path: Path) -> tuple[str, list[str]]:
    """Extract context summary and commands from a JSONL transcript file.

    Returns (context_summary, commands_list) where commands are deduplicated,
    most recent first (up to 5).
    """
    if not transcript_path.exists():
        return "", []

    messages: list[dict] = []
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    # Commands: collect all unique Bash tool_use commands (most recent first)
    seen_cmds: set[str] = set()
    recent_commands: list[str] = []
    for msg in reversed(messages):
        if msg.get("type") == "tool_use":
            tool_name = (msg.get("name") or "").lower()
            if tool_name == "bash":
                cmd = (msg.get("input") or {}).get("command", "")
                if cmd and cmd not in seen_cmds:
                    seen_cmds.add(cmd)
                    recent_commands.append(cmd)

    # Context: all assistant messages + last user message, full text
    assistant_texts: list[str] = []
    last_user_text: str = ""
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        text = ""
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            text_parts = [
                part.get("text", "").strip()
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            text = " ".join(p for p in text_parts if p)
        if not text:
            continue
        if role == "assistant":
            assistant_texts.append(text)
        elif role == "user":
            last_user_text = text

    context = ""
    if assistant_texts:
        full_text = " ".join(assistant_texts)
        sentences = re.split(r"[.!?]+", full_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        context = ". ".join(sentences)
        if context and context[-1] not in ".!?":
            context += "."
    if last_user_text and context:
        context = last_user_text.strip() + " → " + context

    return context, recent_commands


def _build_section_block(data_line: str, sub_dict: dict[str, str]) -> str:
    """Build the full <!-- sessionmark:start...end --> block."""
    if sub_dict:
        dict_str = ",".join(f"{k}={v}" for k, v in sub_dict.items())
        return (
            f"<!-- sessionmark:start\ndict:{dict_str}\n-->\n"
            f"{data_line}\n<!-- sessionmark:end -->"
        )
    return f"<!-- sessionmark:start\n-->\n{data_line}\n<!-- sessionmark:end -->"


def update_context_section(
    config_file: Path,
    compressed: str,
    mode: Literal["append_section", "full_override"],
) -> bool:
    """Update the sessionmark section in a config file. Returns True if modified."""
    if mode == "full_override":
        new_content = f"You are a helpful AI coding assistant.\n\n{SCHEMA_LINE}\n\n{compressed}\n"
        if config_file.exists() and config_file.read_text(encoding="utf-8") == new_content:
            return False
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(new_content, encoding="utf-8")
        return True

    # append_section mode
    if config_file.exists():
        content = config_file.read_text(encoding="utf-8")
        if SECTION_RE.search(content):
            new_content = SECTION_RE.sub(compressed, content)
            if new_content == content:
                return False
            config_file.write_text(new_content, encoding="utf-8")
            return True
        # No existing section — append
        new_content = content.rstrip("\n") + "\n\n" + compressed + "\n"
        config_file.write_text(new_content, encoding="utf-8")
        return True

    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(compressed + "\n", encoding="utf-8")
    return True


def install_section(
    config_file: Path,
    mode: Literal["append_section", "full_override"] = "append_section",
) -> Literal["installed", "already_installed"]:
    """Install schema line and empty sessionmark markers in a config file."""
    empty_block = "<!-- sessionmark:start\n<!-- sessionmark:end -->"

    if config_file.exists():
        content = config_file.read_text(encoding="utf-8")
        if SECTION_RE.search(content):
            return "already_installed"
        if mode == "full_override":
            new_content = (
                f"You are a helpful AI coding assistant.\n\n"
                f"{SCHEMA_LINE}\n\n{empty_block}\n"
            )
            config_file.write_text(new_content, encoding="utf-8")
        else:
            new_content = content.rstrip("\n") + "\n\n" + SCHEMA_LINE + "\n\n" + empty_block + "\n"
            config_file.write_text(new_content, encoding="utf-8")
        return "installed"

    config_file.parent.mkdir(parents=True, exist_ok=True)
    if mode == "full_override":
        config_file.write_text(
            f"You are a helpful AI coding assistant.\n\n{SCHEMA_LINE}\n\n{empty_block}\n",
            encoding="utf-8",
        )
    else:
        config_file.write_text(SCHEMA_LINE + "\n\n" + empty_block + "\n", encoding="utf-8")
    return "installed"


def has_section(config_file: Path) -> bool:
    """Return True if the config file contains a sessionmark section."""
    if not config_file.exists():
        return False
    return bool(SECTION_RE.search(config_file.read_text(encoding="utf-8")))


def clear_section(config_file: Path) -> bool:
    """Remove the sessionmark section from a config file. Returns True if removed."""
    if not config_file.exists():
        return False
    content = config_file.read_text(encoding="utf-8")
    if not SECTION_RE.search(content):
        return False
    new_content = SECTION_RE.sub("", content).strip()
    if new_content:
        new_content += "\n"
    config_file.write_text(new_content, encoding="utf-8")
    return True


def _build_encoding_fields(bm: dict, config_home: Path) -> dict:
    """Build encoding-ready fields dict from a Bookmark dict."""
    branch = bm.get("git_branch") or ""
    head = (bm.get("git_head") or "")[:7]
    repo_root = bm.get("repo_root") or ""

    nxt_parts = [f"cd {repo_root}"] if repo_root else []
    if branch:
        nxt_parts.append(f"git checkout {branch}")
    nxt = " && ".join(nxt_parts)

    # Extract transcript context
    context_summary = ""
    commands: list[str] = []
    if bm.get("transcript_blob"):
        transcript_path = config_home / bm["transcript_blob"]
        context_summary, commands = extract_transcript_context(transcript_path)

    if not context_summary:
        context_summary = (bm.get("goal") or "").replace("\n", " ").strip()

    # Load git-modified files from diff_blob
    files: list[str] = []
    if bm.get("diff_blob"):
        try:
            from bookmark.storage.blobs import BlobStore

            store = BlobStore(config_home)
            raw = store.read(bm["diff_blob"])
            if raw:
                for entry in json.loads(raw):
                    status = entry.get("status", "M")
                    path = entry.get("path", "")
                    if path:
                        files.append(f"{status}:{path}")
        except Exception:
            pass

    # Build todos list
    t_list: list[str] = []
    for todo in bm.get("todos") or []:
        if isinstance(todo, dict):
            done = "1" if todo.get("status") == "done" else "0"
            text = (todo.get("text") or "").replace("|", " ").replace(",", " ")
            if text:
                t_list.append(f"{done}:{text}")

    return {
        "n": bm.get("name") or bm.get("slug") or "",
        "g": (bm.get("goal") or "").replace("\n", " ").strip(),
        "b": branch,
        "h": head,
        "r": bm.get("repo_name") or "",
        "s": bm.get("source") or "",
        "f": files,
        "t": t_list,
        "c": commands,
        "x": context_summary,
        "nxt": nxt,
    }


def update_all_installed(cwd: Path, session: dict) -> list[Path]:
    """Update all installed config files with compressed session context.

    Only updates files that already have a sessionmark section (installed via
    `sessionmark install`). Returns list of paths that were modified.
    Silently skips if no config files are present.
    """
    try:
        from bookmark.config import load_config

        config = load_config()
        config_home = config.home
    except Exception:
        return []

    enc_fields = _build_encoding_fields(session, config_home)

    # Collect all string values for dictionary building
    value_parts: list[str] = [
        enc_fields.get("n") or "",
        enc_fields.get("g") or "",
        enc_fields.get("r") or "",
        enc_fields.get("s") or "",
        enc_fields.get("x") or "",
        enc_fields.get("nxt") or "",
    ]
    value_parts.extend(enc_fields.get("f") or [])
    value_parts.extend(enc_fields.get("t") or [])
    value_parts.extend(enc_fields.get("c") or [])
    session_str = " ".join(v for v in value_parts if v)

    sub_dict = build_dict(session_str)
    data_line = encode_session(enc_fields, sub_dict)
    section_block = _build_section_block(data_line, sub_dict)

    modified: list[Path] = []
    for _agent, cfg in CONFIG_FILES.items():
        config_file = cwd / cfg["path"]
        mode: Literal["append_section", "full_override"] = cfg["mode"]  # type: ignore[assignment]
        if not has_section(config_file):
            continue
        try:
            if update_context_section(config_file, section_block, mode):
                modified.append(config_file)
        except Exception:
            pass

    return modified
