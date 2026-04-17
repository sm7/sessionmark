"""Ollama local LLM provider — §11.3 of design doc."""
from __future__ import annotations

from bookmark.briefing.providers import _build_prompt


class OllamaProvider:
    """Ollama local LLM provider — calls http://localhost:11434/api/generate."""

    def __init__(self, model: str = "qwen2.5-coder:7b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def generate(self, context: dict) -> str:
        import httpx
        prompt = _build_prompt(context)
        resp = httpx.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()
