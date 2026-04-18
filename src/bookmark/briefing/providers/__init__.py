"""Briefing providers package — §11.3 of design doc.

Factory function and shared utilities for briefing providers.
"""
from __future__ import annotations


def _build_prompt(context: dict) -> str:
    """Build a prompt string from bookmark context dict."""
    goal = context.get("goal") or "(no goal)"
    todos = context.get("todos", [])
    pending = [
        t for t in todos
        if getattr(t, "status", t.get("status", "") if isinstance(t, dict) else "") == "pending"
    ]
    transcript = context.get("transcript", [])[-4:]
    files = context.get("open_files", [])

    parts = [
        "Summarize this coding session in 3-5 sentences for a developer returning to it.",
        f"\nGOAL: {goal}",
    ]
    if pending:
        todo_texts = []
        for t in pending[:5]:
            if hasattr(t, "text"):
                todo_texts.append(t.text)
            elif isinstance(t, dict):
                todo_texts.append(t.get("text", ""))
        parts.append("\nOPEN TODOS: " + "; ".join(todo_texts))
    if transcript:
        last = transcript[-1]
        content = last.get("content", "")[:200] if isinstance(last, dict) else ""
        role = last.get("role", "?") if isinstance(last, dict) else "?"
        parts.append(f"\nLAST MESSAGE ({role}): {content}")
    if files:
        file_paths = []
        for f in files[:5]:
            if hasattr(f, "path"):
                file_paths.append(f.path)
            elif isinstance(f, dict):
                file_paths.append(f.get("path", ""))
        parts.append("\nOPEN FILES: " + ", ".join(file_paths))
    parts.append("\nWrite 3-5 sentences only. No preamble.")
    return "\n".join(parts)


def get_provider(uri: str):
    """Parse a provider URI and return the appropriate provider.

    Returns None for "template" or empty string.
    Raises ValueError for unknown provider scheme.
    """
    if not uri or uri == "template":
        return None
    scheme, _, rest = uri.partition(":")
    if scheme == "ollama":
        from .ollama import OllamaProvider
        return OllamaProvider(model=rest)
    elif scheme == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(model=rest)
    elif scheme == "openai":
        from .openai import OpenAIProvider
        return OpenAIProvider(model=rest)
    elif scheme == "google":
        from .google import GoogleProvider
        return GoogleProvider(model=rest)
    elif scheme == "groq":
        from .groq import GroqProvider
        return GroqProvider(model=rest)
    elif scheme == "openai-compat":
        # rest = "http://host:port:model-name"
        parts = rest.rsplit(":", 1)
        url, model = parts[0], parts[1] if len(parts) == 2 else "default"
        from .openai import OpenAIProvider
        return OpenAIProvider(model=model, base_url=url)
    raise ValueError(
        f"Unknown briefing provider scheme: {scheme!r}. "
        f"Valid: template, ollama, anthropic, openai, google, groq, openai-compat"
    )
