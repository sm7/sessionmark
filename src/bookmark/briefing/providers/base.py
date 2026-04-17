"""BriefingProvider protocol — §11.3 of design doc."""
from typing import Protocol, runtime_checkable


@runtime_checkable
class BriefingProvider(Protocol):
    """Anything that can turn a bookmark into a briefing string."""

    def generate(self, context: dict) -> str:
        """Generate a briefing string from bookmark context dict.

        context keys: goal, transcript, todos, open_files, repo_root, git_branch, git_head
        Returns: briefing string (a few sentences)
        Falls back handled by caller.
        """
        ...
