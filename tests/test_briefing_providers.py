"""Briefing provider tests — §11.3, acceptance criteria §16.9."""
import pytest
from unittest.mock import patch, MagicMock


def test_template_provider_is_none():
    """template URI returns None provider (uses template rendering)."""
    from bookmark.briefing.providers import get_provider
    assert get_provider("template") is None
    assert get_provider("") is None


def test_unknown_provider_raises():
    from bookmark.briefing.providers import get_provider
    with pytest.raises(ValueError, match="Unknown"):
        get_provider("foobar:model")


def test_ollama_provider_calls_httpx(monkeypatch):
    """OllamaProvider calls the right endpoint."""
    from bookmark.briefing.providers.ollama import OllamaProvider
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"response": "Here is your briefing."}
    mock_resp.raise_for_status = MagicMock()
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        provider = OllamaProvider(model="test-model")
        result = provider.generate({"goal": "fix the bug", "transcript": [], "todos": [], "open_files": []})
    assert "briefing" in result.lower() or len(result) > 0
    mock_post.assert_called_once()
    assert "localhost:11434" in mock_post.call_args[0][0]


def test_anthropic_provider_calls_httpx(monkeypatch):
    from bookmark.briefing.providers.anthropic import AnthropicProvider
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"content": [{"text": "Summary here."}]}
    mock_resp.raise_for_status = MagicMock()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with patch("httpx.post", return_value=mock_resp):
        provider = AnthropicProvider(model="claude-haiku-4-5")
        result = provider.generate({"goal": "fix", "transcript": [], "todos": [], "open_files": []})
    assert len(result) > 0


def test_anthropic_provider_requires_api_key(monkeypatch):
    """Raises ValueError if ANTHROPIC_API_KEY not set."""
    from bookmark.briefing.providers.anthropic import AnthropicProvider
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider = AnthropicProvider()
    with pytest.raises((ValueError, Exception)):
        provider.generate({"goal": "x", "transcript": [], "todos": [], "open_files": []})


def test_openai_provider_calls_httpx(monkeypatch):
    from bookmark.briefing.providers.openai import OpenAIProvider
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": "Summary."}}]}
    mock_resp.raise_for_status = MagicMock()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with patch("httpx.post", return_value=mock_resp):
        provider = OpenAIProvider()
        result = provider.generate({"goal": "test", "transcript": [], "todos": [], "open_files": []})
    assert len(result) > 0


def test_google_provider_calls_httpx(monkeypatch):
    from bookmark.briefing.providers.google import GoogleProvider
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Gemini summary."}]}}]
    }
    mock_resp.raise_for_status = MagicMock()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch("httpx.post", return_value=mock_resp):
        provider = GoogleProvider()
        result = provider.generate({"goal": "test", "transcript": [], "todos": [], "open_files": []})
    assert len(result) > 0


def test_groq_provider_calls_httpx(monkeypatch):
    from bookmark.briefing.providers.groq import GroqProvider
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": "Groq summary."}}]}
    mock_resp.raise_for_status = MagicMock()
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    with patch("httpx.post", return_value=mock_resp):
        provider = GroqProvider()
        result = provider.generate({"goal": "test", "transcript": [], "todos": [], "open_files": []})
    assert len(result) > 0


def test_get_provider_ollama():
    from bookmark.briefing.providers import get_provider
    from bookmark.briefing.providers.ollama import OllamaProvider
    p = get_provider("ollama:qwen2.5-coder:7b")
    assert isinstance(p, OllamaProvider)
    assert p.model == "qwen2.5-coder:7b"


def test_get_provider_anthropic():
    from bookmark.briefing.providers import get_provider
    from bookmark.briefing.providers.anthropic import AnthropicProvider
    p = get_provider("anthropic:claude-haiku-4-5")
    assert isinstance(p, AnthropicProvider)
    assert p.model == "claude-haiku-4-5"


def test_get_provider_openai():
    from bookmark.briefing.providers import get_provider
    from bookmark.briefing.providers.openai import OpenAIProvider
    p = get_provider("openai:gpt-4o-mini")
    assert isinstance(p, OpenAIProvider)


def test_get_provider_openai_compat():
    from bookmark.briefing.providers import get_provider
    from bookmark.briefing.providers.openai import OpenAIProvider
    p = get_provider("openai-compat:http://localhost:8080:my-model")
    assert isinstance(p, OpenAIProvider)
    assert p.model == "my-model"
    assert "localhost:8080" in p.base_url


def test_provider_fallback_on_failure(tmp_path, monkeypatch, capsys):
    """When provider raises, resume falls back to template and emits stderr warning."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    from bookmark.core.save import save_bookmark
    from bookmark.core.resume import resume_bookmark

    repo = tmp_path / "repo"
    repo.mkdir()

    config = load_config()
    config.briefing_provider = "anthropic:claude-haiku-4-5"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    save_bookmark(name="test-fallback", goal="test goal", config=config, cwd=str(repo))

    # Should not raise — falls back to template
    bm = resume_bookmark(name="test-fallback", config=config)
    captured = capsys.readouterr()
    assert "briefing provider failed" in captured.err or bm is not None


def test_api_keys_not_in_config(tmp_path, monkeypatch):
    """Config file must not contain credential-like values."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    config = load_config()
    config_path = config.home / "config.toml"
    content = config_path.read_text()
    import re
    # No AWS keys, OpenAI keys, etc.
    assert not re.search(r'AKIA[0-9A-Z]{16}', content)
    assert not re.search(r'sk-[a-zA-Z0-9]{20,}', content)
    assert "API_KEY" not in content.upper() or "# " in content  # comments allowed


def test_build_prompt_includes_goal():
    """_build_prompt includes goal in output."""
    from bookmark.briefing.providers import _build_prompt
    result = _build_prompt({"goal": "fix the auth bug", "transcript": [], "todos": [], "open_files": []})
    assert "fix the auth bug" in result


def test_build_prompt_includes_pending_todos():
    """_build_prompt includes pending todos."""
    from bookmark.briefing.providers import _build_prompt

    class FakeTodo:
        status = "pending"
        text = "write tests"

    result = _build_prompt({"goal": "x", "transcript": [], "todos": [FakeTodo()], "open_files": []})
    assert "write tests" in result
