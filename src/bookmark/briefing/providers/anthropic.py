"""Anthropic Claude provider — §11.3 of design doc."""
from __future__ import annotations

from bookmark.briefing.providers import _build_prompt


class AnthropicProvider:
    """Anthropic Claude provider — calls messages API."""

    def __init__(self, model: str = "claude-haiku-4-5"):
        self.model = model

    def generate(self, context: dict) -> str:
        import httpx
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        prompt = _build_prompt(context)
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            json={"model": self.model, "max_tokens": 256,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()
