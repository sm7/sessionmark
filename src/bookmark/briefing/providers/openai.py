"""OpenAI provider — §11.3 of design doc."""
from __future__ import annotations

from bookmark.briefing.providers import _build_prompt


class OpenAIProvider:
    """OpenAI (and OpenAI-compatible) provider."""

    def __init__(self, model: str = "gpt-4o-mini", base_url: str = "https://api.openai.com/v1"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def generate(self, context: dict) -> str:
        import httpx
        import os
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
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
