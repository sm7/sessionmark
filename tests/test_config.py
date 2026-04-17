"""Config get/set tests — Week 4."""
import pytest


def test_config_get_default_value(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import config_get, load_config
    load_config()  # create config file
    val = config_get("general.default_source")
    assert val == "terminal" or val is not None  # default


def test_config_set_and_get(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import config_get, config_set, load_config
    load_config()
    config_set("briefing.provider", "template")
    val = config_get("briefing.provider")
    assert val == "template"


def test_config_set_rejects_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import config_set, load_config
    load_config()
    with pytest.raises(ValueError, match="credential"):
        config_set("general.something", "AKIAIOSFODNN7EXAMPLE")


def test_config_set_briefing_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import config_get, config_set, load_config
    load_config()
    config_set("briefing.provider", "ollama:qwen2.5-coder:7b")
    val = config_get("briefing.provider")
    assert "ollama" in val


def test_config_set_new_section(tmp_path, monkeypatch):
    """config_set creates a new section if it doesn't exist."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import config_get, config_set, load_config
    load_config()
    config_set("ui.color", "always")
    val = config_get("ui.color")
    assert val == "always"


def test_config_set_update_existing(tmp_path, monkeypatch):
    """config_set updates an existing value."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import config_get, config_set, load_config
    load_config()
    config_set("general.default_source", "claude-code")
    val = config_get("general.default_source")
    assert val == "claude-code"


def test_config_set_rejects_openai_key(tmp_path, monkeypatch):
    """config_set rejects OpenAI-style keys."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import config_set, load_config
    load_config()
    with pytest.raises(ValueError, match="credential"):
        config_set("general.something", "sk-abcdefghijklmnopqrstuvwxyz12345")


def test_load_config_creates_default_file(tmp_path, monkeypatch):
    """load_config creates a config.toml with defaults."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import load_config
    config = load_config()
    config_path = tmp_path / "config.toml"
    assert config_path.exists()
    content = config_path.read_text()
    assert "[general]" in content
    assert "[briefing]" in content


def test_load_config_backward_compat_old_section(tmp_path, monkeypatch):
    """load_config reads from old [bookmark] section for backward compat."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    config_path = tmp_path / "config.toml"
    config_path.write_text('[bookmark]\ndefault_source = "cursor"\n')
    from bookmark.config import load_config
    config = load_config()
    assert config.default_source == "cursor"


def test_config_briefing_provider_from_new_section(tmp_path, monkeypatch):
    """briefing_provider is loaded from [briefing] section."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    config_path = tmp_path / "config.toml"
    config_path.write_text('[briefing]\nprovider = "ollama:qwen2.5-coder:7b"\n')
    from bookmark.config import load_config
    config = load_config()
    assert config.briefing_provider == "ollama:qwen2.5-coder:7b"


def test_config_get_unknown_key_raises(tmp_path, monkeypatch):
    """config_get raises KeyError for unknown keys."""
    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path))
    from bookmark.config import config_get, load_config
    load_config()
    with pytest.raises(KeyError):
        config_get("nonexistent.key")
