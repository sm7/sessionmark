"""AgentCapture protocol — §11.7 of design doc."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AgentCapture(Protocol):
    """Protocol that all agent capture readers must implement."""

    def read_recent_transcript(self, cwd: str, n_messages: int = 20) -> list[dict]:
        """Return last n_messages from the most recent session in cwd.

        Each message: {"role": "user"|"assistant", "content": str, "timestamp": str?}
        Returns [] on any failure.
        """
        ...


# Legacy protocol kept for backward compat
@runtime_checkable
class AgentAdapter(Protocol):
    """Protocol that all agent adapters must implement."""

    source: str  # e.g. "claude-code", "cursor", "terminal"

    def read_transcript(self) -> list[dict]:
        """Return a list of message dicts: {role, content, timestamp}."""
        ...

    def read_session_id(self) -> str | None:
        """Return the agent session ID if available."""
        ...
