"""Installation tests — new config-file-based context injection design."""

import pytest


def test_install_claude_code(tmp_path):
    from bookmark.install.installer import install_for_agent

    result = install_for_agent("claude-code", cwd=str(tmp_path))
    assert result["action"] == "installed"
    dest = tmp_path / "CLAUDE.md"
    assert dest.exists()
    content = dest.read_text()
    assert "sessionmark-schema" in content
    assert "<!-- sessionmark:start" in content


def test_install_idempotent(tmp_path):
    from bookmark.install.installer import install_for_agent

    r1 = install_for_agent("claude-code", cwd=str(tmp_path))
    r2 = install_for_agent("claude-code", cwd=str(tmp_path))
    assert r1["action"] == "installed"
    assert r2["action"] == "already_installed"


def test_install_cursor(tmp_path):
    from bookmark.install.installer import install_for_agent

    result = install_for_agent("cursor", cwd=str(tmp_path))
    assert result["action"] == "installed"
    dest = tmp_path / ".cursor" / "rules" / "sessionmark.mdc"
    assert dest.exists()


def test_install_codex(tmp_path):
    from bookmark.install.installer import install_for_agent

    result = install_for_agent("codex", cwd=str(tmp_path))
    assert result["action"] == "installed"
    dest = tmp_path / "AGENTS.md"
    assert dest.exists()


def test_install_github_copilot(tmp_path):
    from bookmark.install.installer import install_for_agent

    result = install_for_agent("github-copilot", cwd=str(tmp_path))
    assert result["action"] == "installed"
    dest = tmp_path / ".github" / "copilot-instructions.md"
    assert dest.exists()


def test_install_windsurf(tmp_path):
    from bookmark.install.installer import install_for_agent

    result = install_for_agent("windsurf", cwd=str(tmp_path))
    assert result["action"] == "installed"
    dest = tmp_path / ".windsurf" / "rules" / "sessionmark.md"
    assert dest.exists()


def test_install_gemini(tmp_path):
    from bookmark.install.installer import install_for_agent

    result = install_for_agent("gemini", cwd=str(tmp_path))
    assert result["action"] == "installed"
    dest = tmp_path / ".gemini" / "system.md"
    assert dest.exists()
    content = dest.read_text()
    # Gemini gets a full system prompt wrapper
    assert "helpful AI coding assistant" in content
    assert "sessionmark-schema" in content


def test_install_all(tmp_path):
    from bookmark.install.installer import install_for_all

    results = install_for_all(cwd=str(tmp_path))
    assert len(results) == 6  # all 6 agents
    actions = [r["action"] for r in results]
    assert all(a in ("installed", "already_installed", "skipped") for a in actions)


def test_install_dry_run(tmp_path):
    from bookmark.install.installer import install_for_agent

    result = install_for_agent("claude-code", cwd=str(tmp_path), dry_run=True)
    assert result["action"] == "dry_run"
    dest = tmp_path / "CLAUDE.md"
    assert not dest.exists()


def test_install_unknown_agent(tmp_path):
    from bookmark.install.installer import install_for_agent

    with pytest.raises(ValueError, match="Unknown agent"):
        install_for_agent("unknown-agent", cwd=str(tmp_path))


def test_list_installs(tmp_path):
    from bookmark.install.installer import install_for_agent, list_installs

    install_for_agent("claude-code", cwd=str(tmp_path))
    listing = list_installs(cwd=str(tmp_path))
    claude = next(x for x in listing if x["agent"] == "claude-code")
    assert claude["installed"] is True
    # Other agents not installed
    codex = next(x for x in listing if x["agent"] == "codex")
    assert codex["installed"] is False


def test_list_installs_all_agents_present(tmp_path):
    from bookmark.install.installer import AGENTS, install_for_all, list_installs

    install_for_all(cwd=str(tmp_path))
    listing = list_installs(cwd=str(tmp_path))
    agent_names = [e["agent"] for e in listing]
    for agent in AGENTS:
        assert agent in agent_names
    assert all(e["installed"] for e in listing)


def test_install_appends_to_existing_file(tmp_path):
    """Installing onto an existing file appends the schema + markers without overwriting."""
    from bookmark.install.installer import install_for_agent

    dest = tmp_path / "CLAUDE.md"
    dest.write_text("# My Project\n\nThis is my existing docs.\n", encoding="utf-8")

    result = install_for_agent("claude-code", cwd=str(tmp_path))
    assert result["action"] == "installed"
    content = dest.read_text()
    # Original content preserved
    assert "My Project" in content
    # Schema and markers appended
    assert "sessionmark-schema" in content
    assert "<!-- sessionmark:start" in content
