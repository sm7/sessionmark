"""bookmark.capture.agents — agent-specific transcript adapters.

See design doc §5, §11.7 for the agent capture overview.
"""
from __future__ import annotations


def get_agent_reader(source: str):
    """Return an agent reader for the given source, or None.

    Each reader has a read_recent_transcript(cwd, n_messages=20) method.
    Returns None for unknown/unsupported sources.
    """
    if source == "claude-code":
        from .claude_code import read_recent_transcript as _fn

        class _Reader:
            def read_recent_transcript(self, cwd: str, n: int = 20) -> list[dict]:
                return _fn(cwd, n)

        return _Reader()

    elif source == "cursor":
        from .cursor import read_recent_transcript as _fn

        class _Reader:  # type: ignore[no-redef]
            def read_recent_transcript(self, cwd: str, n: int = 20) -> list[dict]:
                return _fn(cwd, n)

        return _Reader()

    elif source == "codex":
        from .codex import read_recent_transcript as _fn

        class _Reader:  # type: ignore[no-redef]
            def read_recent_transcript(self, cwd: str, n: int = 20) -> list[dict]:
                return _fn(cwd, n)

        return _Reader()

    elif source == "gemini":
        from .gemini import read_recent_transcript as _fn

        class _Reader:  # type: ignore[no-redef]
            def read_recent_transcript(self, cwd: str, n: int = 20) -> list[dict]:
                return _fn(cwd, n)

        return _Reader()

    elif source == "aider":
        from .aider import read_recent_transcript as _fn

        class _Reader:  # type: ignore[no-redef]
            def read_recent_transcript(self, cwd: str, n: int = 20) -> list[dict]:
                return _fn(cwd, n)

        return _Reader()

    elif source == "github-copilot":
        from .github_copilot import read_recent_transcript as _fn

        class _Reader:  # type: ignore[no-redef]
            def read_recent_transcript(self, cwd: str, n: int = 20) -> list[dict]:
                return _fn(cwd, n)

        return _Reader()

    elif source == "jetbrains":
        from .jetbrains import read_recent_transcript as _fn

        class _Reader:  # type: ignore[no-redef]
            def read_recent_transcript(self, cwd: str, n: int = 20) -> list[dict]:
                return _fn(cwd, n)

        return _Reader()

    return None
