"""Secret redaction for bookmark-cli.

Scans text blobs for common secret patterns and replaces them with
[REDACTED:<kind>] tokens. This module is called before *any* blob write.
Non-negotiable: no secrets ever hit persistent storage.

See design doc §9 for redaction requirements.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Patterns — ordered from most-specific to least-specific
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # AWS access key
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED:aws]"),
    # OpenAI secret key
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "[REDACTED:openai]"),
    # GitHub tokens
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "[REDACTED:github]"),
    (re.compile(r"gho_[a-zA-Z0-9]{36}"), "[REDACTED:github]"),
    (re.compile(r"ghs_[a-zA-Z0-9]{36}"), "[REDACTED:github]"),
    # Slack tokens
    (re.compile(r"xox[baprs]-[a-zA-Z0-9\-]+"), "[REDACTED:slack]"),
    # Bearer tokens: Authorization: Bearer <token>
    (
        re.compile(
            r"(?i)(?:authorization)\s*:\s*Bearer\s+([A-Za-z0-9+/=_\-]{20,200})"
        ),
        lambda m: m.group(0).replace(m.group(1), "[REDACTED:bearer]"),  # type: ignore[arg-type]
    ),
    # Generic: high-entropy values after common secret key names
    # Matches token=, password=, secret=, api_key=, authorization: followed by
    # a base64-ish string of 32-100 chars.
    (
        re.compile(
            r"(?i)(?:token|password|secret|api_key|authorization)\s*[:=]\s*"
            r"([A-Za-z0-9+/=_\-]{32,100})"
        ),
        lambda m: m.group(0).replace(m.group(1), "[REDACTED:generic]"),  # type: ignore[arg-type]
    ),
]


def redact(text: str) -> str:
    """Return *text* with all detected secrets replaced by redaction tokens.

    This function is pure (no I/O) so it is easy to unit-test.
    """
    for pattern, replacement in _PATTERNS:
        if callable(replacement):
            text = pattern.sub(replacement, text)  # type: ignore[arg-type]
        else:
            text = pattern.sub(replacement, text)
    return text


def is_env_file(path: str) -> bool:
    """Return True if *path* looks like a .env file that must never be read."""
    import os

    basename = os.path.basename(path)
    return basename == ".env" or basename.startswith(".env.")
