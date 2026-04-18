"""Installation idempotency tests — §11.4 of design doc."""
import pytest


def test_install_claude_code(tmp_path):
    from bookmark.install.installer import install_for_agent
    result = install_for_agent("claude-code", cwd=str(tmp_path))
    assert result["action"] == "installed"
    dest = tmp_path / ".claude" / "skills" / "bookmark" / "SKILL.md"
    assert dest.exists()
    content = dest.read_text()
    assert "bookmark save" in content


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
    dest = tmp_path / ".cursor" / "rules" / "bookmark.mdc"
    assert dest.exists()


def test_install_codex(tmp_path):
    from bookmark.install.installer import install_for_agent
    result = install_for_agent("codex", cwd=str(tmp_path))
    assert result["action"] == "installed"


def test_install_all(tmp_path):
    from bookmark.install.installer import install_for_all
    results = install_for_all(cwd=str(tmp_path))
    assert len(results) == 6  # all 6 agents
    actions = [r["action"] for r in results]
    assert all(a in ("installed", "skipped") for a in actions)


def test_install_dry_run(tmp_path):
    from bookmark.install.installer import install_for_agent
    result = install_for_agent("claude-code", cwd=str(tmp_path), dry_run=True)
    assert result["action"] == "dry_run"
    # File must NOT exist after dry run
    dest = tmp_path / ".claude" / "skills" / "bookmark" / "SKILL.md"
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
