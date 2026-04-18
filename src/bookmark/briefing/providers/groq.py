"""Groq provider — §11.3 of design doc."""
from __future__ import annotations

from bookmark.briefing.providers import _build_prompt


class GroqProvider:
    """Groq provider — same API shape as OpenAI."""

    def __init__(self, model: str = "llama-3.3-70b"):
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"

    def generate(self, context: dict) -> str:
        import os

        import httpx
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set")
        prompt = _build_prompt(context)
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 256},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
