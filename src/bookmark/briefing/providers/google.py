"""Google Gemini provider — §11.3 of design doc."""
from __future__ import annotations

from bookmark.briefing.providers import _build_prompt


class GoogleProvider:
    """Google Gemini provider."""

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model

    def generate(self, context: dict) -> str:
        import os

        import httpx
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        prompt = _build_prompt(context)
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
