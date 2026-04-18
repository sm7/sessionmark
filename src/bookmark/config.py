"""Configuration loading for bookmark-cli.

Loads ~/.bookmark/config.toml (or $BOOKMARK_HOME/config.toml) using tomllib.
Returns a Config pydantic model with sensible defaults.
Creates the config file with defaults on first run.

See design doc §13, §15 for configuration details.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Config(BaseModel):
    """Top-level configuration model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    home: Path = Field(default_factory=lambda: _default_home())

    # [general]
    default_source: str = "terminal"
    max_transcript_messages: int = 20
    recent_file_window_seconds: int = 7200

    # [capture]
    include_shell_history: bool = True
    include_env: bool = True
    include_git_diff: bool = True
    max_diff_bytes: int = 262144

    # [redaction]
    redact_enabled: bool = True

    # [briefing]
    briefing_provider: str = "template"
    briefing_timeout: int = 10

    # [sync]
    sync_enabled: bool = False
    git_remote: str = ""

    # [ui]
    show_source_column: bool = True
    color: str = "auto"

    # Legacy / misc
    blob_compress: bool = True

    # Backward-compat aliases
    llm_provider: str | None = None
    llm_model: str | None = None


def _default_home() -> Path:
    """Return the bookmark home directory from env or default."""
    env = os.environ.get("BOOKMARK_HOME")
    if env:
        return Path(env)
    return Path.home() / ".bookmark"


_DEFAULT_TOML = """\
# bookmark-cli configuration
# See: https://github.com/your-org/bookmark-cli

[general]
default_source = "terminal"
max_transcript_messages = 20
recent_file_window_seconds = 7200

[capture]
include_shell_history = true
include_env = true
include_git_diff = true
max_diff_bytes = 262144

[redaction]
enabled = true

[briefing]
provider = "template"
max_summary_sentences = 4
timeout_seconds = 10

[sync]
enabled = false
git_remote = ""

[ui]
show_source_column = true
color = "auto"
"""


def load_config() -> Config:
    """Load config from TOML file, creating it with defaults if absent."""
    home = _default_home()
    home.mkdir(parents=True, exist_ok=True)

    config_path = home / "config.toml"
    if not config_path.exists():
        config_path.write_text(_DEFAULT_TOML, encoding="utf-8")

    with config_path.open("rb") as fh:
        raw = tomllib.load(fh)

    # Support both old [bookmark] section and new multi-section layout
    old = raw.get("bookmark", {})
    general = raw.get("general", {})
    capture = raw.get("capture", {})
    redaction = raw.get("redaction", {})
    briefing = raw.get("briefing", {})
    sync = raw.get("sync", {})
    ui = raw.get("ui", {})

    # Resolve briefing_provider: new [briefing] section > old llm_provider
    llm_provider = old.get("llm_provider")
    briefing_provider = briefing.get("provider", old.get("briefing_provider", "template"))
    if llm_provider and briefing_provider == "template":
        briefing_provider = llm_provider

    return Config(
        home=home,
        # general
        default_source=general.get("default_source", old.get("default_source", "terminal")),
        max_transcript_messages=general.get(
            "max_transcript_messages", old.get("max_transcript_messages", 20)
        ),
        recent_file_window_seconds=general.get(
            "recent_file_window_seconds", old.get("recent_file_window_seconds", 7200)
        ),
        # capture
        include_shell_history=capture.get(
            "include_shell_history", old.get("include_shell_history", True)
        ),
        include_env=capture.get("include_env", old.get("include_env", True)),
        include_git_diff=capture.get("include_git_diff", old.get("include_git_diff", True)),
        max_diff_bytes=capture.get("max_diff_bytes", old.get("max_diff_bytes", 262144)),
        # redaction
        redact_enabled=redaction.get("enabled", old.get("redact_enabled", True)),
        # briefing
        briefing_provider=briefing_provider,
        briefing_timeout=briefing.get("timeout_seconds", old.get("briefing_timeout", 10)),
        # sync
        sync_enabled=sync.get("enabled", old.get("sync_enabled", False)),
        git_remote=sync.get("git_remote", old.get("git_remote", "")),
        # ui
        show_source_column=ui.get("show_source_column", old.get("show_source_column", True)),
        color=ui.get("color", old.get("color", "auto")),
        # misc
        blob_compress=old.get("blob_compress", True),
        # backward compat
        llm_provider=llm_provider,
        llm_model=old.get("llm_model"),
    )


# ---------------------------------------------------------------------------
# config get / set helpers
# ---------------------------------------------------------------------------

# Map dot-path keys to (toml_section, toml_key)
_KEY_MAP: dict[str, tuple[str, str]] = {
    "general.default_source": ("general", "default_source"),
    "general.max_transcript_messages": ("general", "max_transcript_messages"),
    "general.recent_file_window_seconds": ("general", "recent_file_window_seconds"),
    "capture.include_shell_history": ("capture", "include_shell_history"),
    "capture.include_env": ("capture", "include_env"),
    "capture.include_git_diff": ("capture", "include_git_diff"),
    "capture.max_diff_bytes": ("capture", "max_diff_bytes"),
    "redaction.enabled": ("redaction", "enabled"),
    "briefing.provider": ("briefing", "provider"),
    "briefing.timeout_seconds": ("briefing", "timeout_seconds"),
    "briefing.max_summary_sentences": ("briefing", "max_summary_sentences"),
    "sync.enabled": ("sync", "enabled"),
    "sync.git_remote": ("sync", "git_remote"),
    "ui.show_source_column": ("ui", "show_source_column"),
    "ui.color": ("ui", "color"),
}


def _config_path() -> Path:
    return _default_home() / "config.toml"


def config_get(key: str) -> str:
    """Get a config value by dot-path key (e.g. 'briefing.provider').

    Returns the value as a string. Raises KeyError if not found.
    """
    path = _config_path()
    if not path.exists():
        load_config()  # creates default

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    # Try new multi-section layout first
    if key in _KEY_MAP:
        section, k = _KEY_MAP[key]
        val = raw.get(section, {}).get(k)
        if val is not None:
            return str(val)
        # Fall through to check defaults via load_config
        cfg = load_config()
        # Map known dot-paths to Config attribute names
        _attr_map = {
            "general.default_source": "default_source",
            "general.max_transcript_messages": "max_transcript_messages",
            "general.recent_file_window_seconds": "recent_file_window_seconds",
            "capture.include_shell_history": "include_shell_history",
            "capture.include_env": "include_env",
            "capture.include_git_diff": "include_git_diff",
            "capture.max_diff_bytes": "max_diff_bytes",
            "redaction.enabled": "redact_enabled",
            "briefing.provider": "briefing_provider",
            "briefing.timeout_seconds": "briefing_timeout",
            "sync.enabled": "sync_enabled",
            "sync.git_remote": "git_remote",
            "ui.show_source_column": "show_source_column",
            "ui.color": "color",
        }
        attr = _attr_map.get(key)
        if attr and hasattr(cfg, attr):
            return str(getattr(cfg, attr))

    # Try direct dot-path navigation in raw dict
    parts = key.split(".")
    node = raw
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"Config key not found: {key!r}")
        node = node[part]
    return str(node)


def config_set(key: str, value: str) -> None:
    """Set a config value by dot-path key.

    Rejects values that look like credentials.
    Raises ValueError for credential-like values.
    """
    from bookmark.redact import redact
    if redact(value) != value:
        raise ValueError(
            "Value looks like a credential — API keys must come from env vars, not config."
        )

    path = _config_path()
    if not path.exists():
        load_config()  # creates default file

    # Determine section and key
    if key in _KEY_MAP:
        section, toml_key = _KEY_MAP[key]
    elif "." in key:
        section, _, toml_key = key.partition(".")
    else:
        raise KeyError(f"Unknown config key: {key!r}. Use dot-path format like 'briefing.provider'")

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    # Format the value for TOML
    # Detect if value is a string (wrap in quotes) or bool/int
    toml_value = _format_toml_value(value)

    new_line = f"{toml_key} = {toml_value}\n"

    # Try to find the section header and then the key within it
    in_section = False
    section_start = -1
    key_line_idx = -1
    section_end = len(lines)  # where this section ends (start of next section or EOF)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == f"[{section}]":
            in_section = True
            section_start = i
            continue
        if in_section:
            # Another section starts
            if stripped.startswith("[") and not stripped.startswith("#"):
                section_end = i
                break
            # Check if key matches
            if re.match(rf"^\s*{re.escape(toml_key)}\s*=", stripped):
                key_line_idx = i
                break

    if key_line_idx >= 0:
        # Replace existing line
        lines[key_line_idx] = new_line
    elif section_start >= 0:
        # Section exists but key not found — insert before section_end
        lines.insert(section_end, new_line)
    else:
        # Section doesn't exist — append it
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"\n[{section}]\n")
        lines.append(new_line)

    path.write_text("".join(lines), encoding="utf-8")


def _format_toml_value(value: str) -> str:
    """Format a string value as a TOML value (quoted string, bool, or int)."""
    # Check if it's a boolean
    if value.lower() in ("true", "false"):
        return value.lower()
    # Check if it's an integer
    try:
        int(value)
        return value
    except ValueError:
        pass
    # Otherwise treat as string — escape backslashes and quotes
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
