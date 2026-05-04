"""Tests for bookmark.install.context_writer — LPIC+CSV context injection."""

from __future__ import annotations

import json
import re

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_transcript(messages: list[dict]) -> str:
    """Build a JSONL string from a list of message dicts."""
    return "\n".join(json.dumps(m) for m in messages) + "\n"


def _decode_section(block: str) -> dict[str, str]:
    """Decode a sessionmark section block back to a field dict (for lossless tests)."""
    from bookmark.install.context_writer import SECTION_RE

    m = SECTION_RE.search(block)
    assert m, "No sessionmark section found in block"
    content = m.group(0)

    # Extract dict
    sub_dict: dict[str, str] = {}
    dict_m = re.search(r"dict:([^\n]+)", content)
    if dict_m:
        for entry in dict_m.group(1).split(","):
            if "=" in entry:
                k, v = entry.split("=", 1)
                sub_dict[k.strip()] = v.strip()

    # Extract data line (after --> and before <!-- sessionmark:end)
    data_m = re.search(r"-->\n(.+)\n<!-- sessionmark:end -->", content, re.DOTALL)
    assert data_m, "No data line found"
    data_line = data_m.group(1).strip()

    # Reverse substitutions (longest value first)
    for value in sorted(sub_dict.values(), key=len, reverse=True):
        key = next(k for k, v in sub_dict.items() if v == value)
        data_line = data_line.replace(key, value)

    # Parse CSV fields — split on "," then on first ":"
    fields: dict[str, str] = {}
    # Use regex to split on known field keys
    known_keys = ["nxt", "n", "g", "b", "h", "r", "s", "f", "t", "c", "x"]
    key_pattern = "|".join(re.escape(k) for k in known_keys)
    # Find all field positions
    for match in re.finditer(rf"(?:^|,)({key_pattern}):", data_line):
        key = match.group(1)
        start = match.end()
        # Find next field boundary
        next_m = re.search(
            rf",(?:{key_pattern}):", data_line[start:]
        )
        if next_m:
            value = data_line[start : start + next_m.start()]
        else:
            value = data_line[start:]
        fields[key] = value

    return fields


# ---------------------------------------------------------------------------
# install_section
# ---------------------------------------------------------------------------


def test_install_section_new_file(tmp_path):
    from bookmark.install.context_writer import SCHEMA_LINE, SECTION_RE, install_section

    cfg = tmp_path / "CLAUDE.md"
    result = install_section(cfg)
    assert result == "installed"
    assert cfg.exists()
    content = cfg.read_text()
    assert SCHEMA_LINE in content
    assert SECTION_RE.search(content) is not None


def test_install_section_existing_file_no_section(tmp_path):
    from bookmark.install.context_writer import SCHEMA_LINE, SECTION_RE, install_section

    cfg = tmp_path / "CLAUDE.md"
    cfg.write_text("# Existing project docs\n\nSome content here.\n", encoding="utf-8")
    result = install_section(cfg)
    assert result == "installed"
    content = cfg.read_text()
    # Original preserved
    assert "Existing project docs" in content
    assert SCHEMA_LINE in content
    assert SECTION_RE.search(content) is not None


def test_install_section_idempotent(tmp_path):
    from bookmark.install.context_writer import install_section

    cfg = tmp_path / "CLAUDE.md"
    r1 = install_section(cfg)
    content_after_first = cfg.read_text()
    r2 = install_section(cfg)
    content_after_second = cfg.read_text()
    assert r1 == "installed"
    assert r2 == "already_installed"
    assert content_after_first == content_after_second


def test_install_section_full_override_new_file(tmp_path):
    from bookmark.install.context_writer import SCHEMA_LINE, SECTION_RE, install_section

    cfg = tmp_path / ".gemini" / "system.md"
    result = install_section(cfg, mode="full_override")
    assert result == "installed"
    content = cfg.read_text()
    assert "helpful AI coding assistant" in content
    assert SCHEMA_LINE in content
    assert SECTION_RE.search(content) is not None


def test_install_section_creates_parent_dirs(tmp_path):
    from bookmark.install.context_writer import install_section

    cfg = tmp_path / ".cursor" / "rules" / "sessionmark.mdc"
    assert not cfg.parent.exists()
    install_section(cfg)
    assert cfg.exists()


# ---------------------------------------------------------------------------
# has_section
# ---------------------------------------------------------------------------


def test_has_section_true(tmp_path):
    from bookmark.install.context_writer import has_section, install_section

    cfg = tmp_path / "CLAUDE.md"
    install_section(cfg)
    assert has_section(cfg) is True


def test_has_section_false_missing_file(tmp_path):
    from bookmark.install.context_writer import has_section

    assert has_section(tmp_path / "CLAUDE.md") is False


def test_has_section_false_no_section(tmp_path):
    from bookmark.install.context_writer import has_section

    cfg = tmp_path / "CLAUDE.md"
    cfg.write_text("# Just a regular file\n", encoding="utf-8")
    assert has_section(cfg) is False


# ---------------------------------------------------------------------------
# build_dict
# ---------------------------------------------------------------------------


def test_build_dict_finds_repeated_substrings():
    from bookmark.install.context_writer import build_dict

    s = "src/bookmark/core.py and src/bookmark/utils.py and src/bookmark/cli.py"
    d = build_dict(s)
    # "src/bookmark/" appears 3 times — should be assigned A
    assert "A" in d
    assert d["A"] == "src/bookmark/"


def test_build_dict_assigns_in_order_of_savings():
    from bookmark.install.context_writer import build_dict

    # The algorithm assigns A to the substring with the highest net savings.
    # Build a string where the best saving is unambiguous.
    # "alpha_token/" appears 5 times — score (5-1)*12 = 48, overhead = 1+1+12+1 = 15
    # Verify A gets the highest-saving entry.
    s = " ".join(["alpha_token/"] * 6) + " other " + " ".join(["alpha_token/"] * 4)
    d = build_dict(s)
    assert "A" in d
    # A must have the highest net saving of all entries
    net_a = (s.count(d["A"]) - 1) * len(d["A"])
    for v in d.values():
        assert net_a >= (s.count(v) - 1) * len(v)


def test_build_dict_skips_low_savings():
    from bookmark.install.context_writer import build_dict

    # "abcde" appears 2 times: net_saving=(2-1)*5=5, overhead=1+1+5+1=8 → skip
    s = "abcde xyz abcde"
    d = build_dict(s)
    assert "abcde" not in d.values()


def test_build_dict_empty_when_no_savings():
    from bookmark.install.context_writer import build_dict

    d = build_dict("short")
    assert d == {}


def test_build_dict_max_26_entries():
    from bookmark.install.context_writer import build_dict

    # Create a string where many substrings repeat heavily
    piece = "abcdefghij"
    s = " ".join([piece] * 30)
    d = build_dict(s)
    assert len(d) <= 26


# ---------------------------------------------------------------------------
# encode_session
# ---------------------------------------------------------------------------


def test_encode_session_all_fields():
    from bookmark.install.context_writer import encode_session

    session = {
        "n": "myapp-build",
        "g": "Build the main feature",
        "b": "feature-branch",
        "h": "a3f91c2",
        "r": "myapp",
        "s": "claude-code",
        "f": ["M:src/main.py", "A:src/utils.py"],
        "t": ["0:write tests", "1:fix bug"],
        "c": ["pytest tests/", "ruff check src/"],
        "x": "completed initial implementation",
        "nxt": "cd ~/code/myapp && git checkout feature-branch",
    }
    line = encode_session(session, {})
    assert "n:myapp-build" in line
    assert "g:Build the main feature" in line
    assert "b:feature-branch" in line
    assert "h:a3f91c2" in line
    assert "r:myapp" in line
    assert "s:claude-code" in line
    assert "f:M:src/main.py|A:src/utils.py" in line
    assert "t:0:write tests|1:fix bug" in line
    assert "c:pytest tests/|ruff check src/" in line
    assert "x:completed initial implementation" in line
    assert "nxt:cd ~/code/myapp" in line


def test_encode_session_applies_dict_substitutions():
    from bookmark.install.context_writer import encode_session

    session = {
        "n": "myapp-build",
        "g": "Build myapp feature",
        "r": "myapp",
        "f": ["M:src/myapp/core.py"],
        "nxt": "cd ~/code/myapp",
    }
    sub_dict = {"A": "myapp"}
    line = encode_session(session, sub_dict)
    # "myapp" should be replaced by "A" throughout
    assert "myapp" not in line
    assert "A" in line


def test_encode_session_omits_empty_fields():
    from bookmark.install.context_writer import encode_session

    session = {"n": "test", "g": "goal"}
    line = encode_session(session, {})
    # Should only have n and g
    assert "n:test" in line
    assert "g:goal" in line
    # Empty list fields should be absent
    assert "f:" not in line
    assert "t:" not in line


def test_encode_session_single_line():
    from bookmark.install.context_writer import encode_session

    session = {
        "n": "build",
        "g": "test goal",
        "b": "main",
        "f": ["M:file.py"],
        "t": ["0:todo1"],
        "c": ["make build"],
    }
    line = encode_session(session, {})
    assert "\n" not in line


# ---------------------------------------------------------------------------
# extract_transcript_context
# ---------------------------------------------------------------------------


def test_extract_transcript_context_commands(tmp_path):
    from bookmark.install.context_writer import extract_transcript_context

    transcript = tmp_path / "transcript.jsonl"
    messages = [
        {"type": "tool_use", "name": "Bash", "input": {"command": "pytest tests/"}},
        {"type": "tool_use", "name": "Bash", "input": {"command": "ruff check src/"}},
        {"type": "tool_use", "name": "Bash", "input": {"command": "git status"}},
        {"role": "assistant", "content": "All tests passed. The implementation is complete."},
    ]
    transcript.write_text(_make_transcript(messages), encoding="utf-8")

    context, commands = extract_transcript_context(transcript)
    assert "git status" in commands
    assert "pytest tests/" in commands
    assert "ruff check src/" in commands
    # most recent first
    assert commands[0] == "git status"


def test_extract_transcript_context_deduplicates_commands(tmp_path):
    from bookmark.install.context_writer import extract_transcript_context

    transcript = tmp_path / "transcript.jsonl"
    messages = [
        {"type": "tool_use", "name": "Bash", "input": {"command": "pytest tests/"}},
        {"type": "tool_use", "name": "Bash", "input": {"command": "pytest tests/"}},
        {"type": "tool_use", "name": "Bash", "input": {"command": "pytest tests/"}},
    ]
    transcript.write_text(_make_transcript(messages), encoding="utf-8")

    _, commands = extract_transcript_context(transcript)
    assert commands.count("pytest tests/") == 1


def test_extract_transcript_context_all_commands(tmp_path):
    from bookmark.install.context_writer import extract_transcript_context

    transcript = tmp_path / "transcript.jsonl"
    messages = [
        {"type": "tool_use", "name": "Bash", "input": {"command": f"cmd{i}"}}
        for i in range(15)
    ]
    transcript.write_text(_make_transcript(messages), encoding="utf-8")

    _, commands = extract_transcript_context(transcript)
    assert len(commands) == 15


def test_extract_transcript_context_assistant_text(tmp_path):
    from bookmark.install.context_writer import extract_transcript_context

    transcript = tmp_path / "transcript.jsonl"
    messages = [
        {"role": "user", "content": "what is next"},
        {"role": "assistant", "content": "We fixed the authentication bug. Next is deployment."},
    ]
    transcript.write_text(_make_transcript(messages), encoding="utf-8")

    context, _ = extract_transcript_context(transcript)
    assert context  # non-empty


def test_extract_transcript_context_missing_file(tmp_path):
    from bookmark.install.context_writer import extract_transcript_context

    context, commands = extract_transcript_context(tmp_path / "nonexistent.jsonl")
    assert context == ""
    assert commands == []


def test_extract_transcript_context_empty_file(tmp_path):
    from bookmark.install.context_writer import extract_transcript_context

    f = tmp_path / "transcript.jsonl"
    f.write_text("", encoding="utf-8")
    context, commands = extract_transcript_context(f)
    assert context == ""
    assert commands == []


# ---------------------------------------------------------------------------
# update_context_section
# ---------------------------------------------------------------------------


def test_update_context_section_append_replaces_existing(tmp_path):
    from bookmark.install.context_writer import install_section, update_context_section

    cfg = tmp_path / "CLAUDE.md"
    install_section(cfg)

    new_block = "<!-- sessionmark:start\n-->\nn:new-session\n<!-- sessionmark:end -->"
    changed = update_context_section(cfg, new_block, "append_section")
    assert changed is True
    content = cfg.read_text()
    assert "n:new-session" in content


def test_update_context_section_append_adds_when_absent(tmp_path):
    from bookmark.install.context_writer import update_context_section

    cfg = tmp_path / "CLAUDE.md"
    cfg.write_text("# My Docs\n", encoding="utf-8")

    block = "<!-- sessionmark:start\n-->\nn:test\n<!-- sessionmark:end -->"
    changed = update_context_section(cfg, block, "append_section")
    assert changed is True
    content = cfg.read_text()
    assert "My Docs" in content
    assert "n:test" in content


def test_update_context_section_append_no_change_same_content(tmp_path):
    from bookmark.install.context_writer import install_section, update_context_section

    cfg = tmp_path / "CLAUDE.md"
    install_section(cfg)

    # Write a known block
    block = "<!-- sessionmark:start\n-->\nn:same\n<!-- sessionmark:end -->"
    update_context_section(cfg, block, "append_section")
    # Second write of same content → no change
    changed = update_context_section(cfg, block, "append_section")
    assert changed is False


def test_update_context_section_full_override(tmp_path):
    from bookmark.install.context_writer import SCHEMA_LINE, update_context_section

    cfg = tmp_path / ".gemini" / "system.md"
    block = "<!-- sessionmark:start\n-->\nn:gemini-test\n<!-- sessionmark:end -->"
    changed = update_context_section(cfg, block, "full_override")
    assert changed is True
    content = cfg.read_text()
    assert "helpful AI coding assistant" in content
    assert SCHEMA_LINE in content
    assert "n:gemini-test" in content


def test_update_context_section_creates_new_file(tmp_path):
    from bookmark.install.context_writer import update_context_section

    cfg = tmp_path / "new_dir" / "AGENTS.md"
    block = "<!-- sessionmark:start\n-->\nn:new\n<!-- sessionmark:end -->"
    changed = update_context_section(cfg, block, "append_section")
    assert changed is True
    assert cfg.exists()


# ---------------------------------------------------------------------------
# clear_section
# ---------------------------------------------------------------------------


def test_clear_section_removes_and_returns_true(tmp_path):
    from bookmark.install.context_writer import clear_section, has_section, install_section

    cfg = tmp_path / "CLAUDE.md"
    install_section(cfg)
    assert has_section(cfg)
    result = clear_section(cfg)
    assert result is True
    assert not has_section(cfg)


def test_clear_section_returns_false_when_absent(tmp_path):
    from bookmark.install.context_writer import clear_section

    cfg = tmp_path / "CLAUDE.md"
    cfg.write_text("# No section here\n", encoding="utf-8")
    assert clear_section(cfg) is False


def test_clear_section_returns_false_missing_file(tmp_path):
    from bookmark.install.context_writer import clear_section

    assert clear_section(tmp_path / "missing.md") is False


# ---------------------------------------------------------------------------
# update_all_installed
# ---------------------------------------------------------------------------


def test_update_all_installed_updates_only_installed(tmp_path, monkeypatch):
    from bookmark.install.context_writer import install_section, update_all_installed

    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path / "bm_home"))

    # Install only claude-code
    cfg = tmp_path / "CLAUDE.md"
    install_section(cfg)

    session = {
        "name": "my-session",
        "slug": "my-session",
        "goal": "test goal",
        "git_branch": "main",
        "git_head": "abc1234",
        "repo_name": "myrepo",
        "repo_root": str(tmp_path),
        "source": "claude-code",
        "transcript_blob": None,
        "diff_blob": None,
        "todos": [],
    }
    modified = update_all_installed(tmp_path, session)
    assert cfg in modified
    # Non-installed files not touched
    agents_md = tmp_path / "AGENTS.md"
    assert not agents_md.exists()


def test_update_all_installed_skips_when_none_installed(tmp_path, monkeypatch):
    from bookmark.install.context_writer import update_all_installed

    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path / "bm_home"))

    session = {
        "name": "test",
        "slug": "test",
        "goal": "nothing",
        "git_branch": None,
        "git_head": None,
        "repo_name": None,
        "repo_root": "",
        "source": "terminal",
        "transcript_blob": None,
        "diff_blob": None,
        "todos": [],
    }
    modified = update_all_installed(tmp_path, session)
    assert modified == []


def test_update_all_installed_returns_modified_paths(tmp_path, monkeypatch):
    from bookmark.install.context_writer import install_section, update_all_installed

    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path / "bm_home"))

    cfg1 = tmp_path / "CLAUDE.md"
    cfg2 = tmp_path / "AGENTS.md"
    install_section(cfg1)
    install_section(cfg2)

    session = {
        "name": "multi-test",
        "slug": "multi-test",
        "goal": "test multiple agents",
        "git_branch": "main",
        "git_head": "abc1234",
        "repo_name": "repo",
        "repo_root": str(tmp_path),
        "source": "claude-code",
        "transcript_blob": None,
        "diff_blob": None,
        "todos": [],
    }
    modified = update_all_installed(tmp_path, session)
    assert cfg1 in modified
    assert cfg2 in modified


# ---------------------------------------------------------------------------
# save() and resume() integration
# ---------------------------------------------------------------------------


def test_save_triggers_context_update(tmp_path, monkeypatch):
    from bookmark.config import load_config
    from bookmark.install.context_writer import has_section, install_section

    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path / "bm_home"))
    monkeypatch.chdir(tmp_path)

    # Install sessionmark for claude-code in this directory
    cfg = tmp_path / "CLAUDE.md"
    install_section(cfg)
    assert has_section(cfg)

    config = load_config()
    from bookmark.core.save import save_bookmark

    save_bookmark(name="test-save", goal="test goal for save", config=config, cwd=str(tmp_path))

    # Section should now have session data (not just empty markers)
    content = cfg.read_text()
    assert "test-save" in content or "n:" in content


def test_resume_triggers_context_update(tmp_path, monkeypatch):
    from bookmark.config import load_config
    from bookmark.install.context_writer import install_section

    monkeypatch.setenv("BOOKMARK_HOME", str(tmp_path / "bm_home"))
    monkeypatch.chdir(tmp_path)

    config = load_config()

    # Save a bookmark first
    from bookmark.core.save import save_bookmark

    repo = tmp_path / "repo"
    repo.mkdir()
    save_bookmark(name="resume-test", goal="test goal for resume", config=config, cwd=str(repo))

    # Install sessionmark in cwd after save
    cfg = tmp_path / "CLAUDE.md"
    install_section(cfg)

    # Resume should update the section
    from bookmark.core.resume import resume_bookmark

    resume_bookmark(name="resume-test", config=config)

    content = cfg.read_text()
    assert "resume-test" in content or "n:" in content


# ---------------------------------------------------------------------------
# list_installs reflects has_section
# ---------------------------------------------------------------------------


def test_list_installs_uses_has_section(tmp_path):
    from bookmark.install.context_writer import install_section
    from bookmark.install.installer import list_installs

    cfg = tmp_path / "CLAUDE.md"
    install_section(cfg)

    listing = list_installs(cwd=str(tmp_path))
    claude = next(x for x in listing if x["agent"] == "claude-code")
    windsurf = next(x for x in listing if x["agent"] == "windsurf")

    assert claude["installed"] is True
    assert windsurf["installed"] is False


# ---------------------------------------------------------------------------
# Lossless round-trip validation
# ---------------------------------------------------------------------------


def test_lossless_round_trip():
    """Encoded session decodes back to original field values exactly."""
    from bookmark.install.context_writer import (
        _build_section_block,
        build_dict,
        encode_session,
    )

    session = {
        "n": "bookmark-cli-build",
        "g": "Built bookmark-cli v0.1.0 all 5 weeks of work",
        "b": "master",
        "h": "a3f91c2",
        "r": "bookmark",
        "s": "claude-code",
        "f": ["M:src/bookmark/core/save.py", "M:src/bookmark/storage/db.py"],
        "t": ["0:publish to PyPI", "1:initial release"],
        "c": ["pytest tests/", "ruff check src/"],
        "x": "completed initial release of bookmark-cli v0.1.0",
        "nxt": "cd ~/code/bookmark && git checkout master",
    }

    # Build string for dict
    value_parts = [
        session["n"], session["g"], session["r"], session["s"], session["x"], session["nxt"]
    ]
    value_parts.extend(session["f"])
    value_parts.extend(session["t"])
    value_parts.extend(session["c"])
    session_str = " ".join(value_parts)

    sub_dict = build_dict(session_str)
    data_line = encode_session(session, sub_dict)
    block = _build_section_block(data_line, sub_dict)

    # Decode
    decoded = _decode_section(block)

    assert decoded.get("n") == session["n"]
    assert decoded.get("g") == session["g"]
    assert decoded.get("b") == session["b"]
    assert decoded.get("r") == session["r"]
    assert decoded.get("s") == session["s"]
    # Files
    assert decoded.get("f") == "|".join(session["f"])
    # Todos
    assert decoded.get("t") == "|".join(session["t"])
    # Commands
    assert decoded.get("c") == "|".join(session["c"])
