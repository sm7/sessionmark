"""Per-agent fallback reader tests — §11.7 of design doc."""
import json
from pathlib import Path


def test_claude_code_reader_empty_when_no_sessions(tmp_path):
    from bookmark.capture.agents.claude_code import read_recent_transcript
    result = read_recent_transcript(str(tmp_path / "project"), _base_dir=tmp_path)
    assert result == []


def test_claude_code_reader_finds_matching_session(tmp_path):
    """Finds session by cwd stored in the jsonl."""
    # Set up fake ~/.claude/projects/ structure
    claude_home = tmp_path / ".claude" / "projects" / "abc123"
    claude_home.mkdir(parents=True)
    session_file = claude_home / "session-001.jsonl"

    project_cwd = str(tmp_path / "myproject")
    lines = [
        json.dumps({"cwd": project_cwd, "type": "meta"}),
        json.dumps({"type": "say", "say": "user", "text": "fix the bug"}),
        json.dumps({"type": "say", "say": "assistant", "text": "Here's the fix"}),
    ]
    session_file.write_text("\n".join(lines))

    from bookmark.capture.agents.claude_code import read_recent_transcript
    result = read_recent_transcript(project_cwd, _base_dir=tmp_path)
    assert len(result) == 2
    assert result[0]["role"] == "user"
    assert "fix the bug" in result[0]["content"]


def test_claude_code_reader_no_match_returns_empty(tmp_path):
    """Returns empty list when cwd doesn't match any session."""
    claude_home = tmp_path / ".claude" / "projects" / "abc123"
    claude_home.mkdir(parents=True)
    session_file = claude_home / "session-001.jsonl"

    # Session has a different cwd
    lines = [
        json.dumps({"cwd": "/some/other/path", "type": "meta"}),
        json.dumps({"type": "say", "say": "user", "text": "hello"}),
    ]
    session_file.write_text("\n".join(lines))

    from bookmark.capture.agents.claude_code import read_recent_transcript
    result = read_recent_transcript(str(tmp_path / "myproject"), _base_dir=tmp_path)
    assert result == []


def test_aider_reader_parses_history(tmp_path):
    """Aider reader parses .aider.chat.history.md."""
    history = tmp_path / ".aider.chat.history.md"
    history.write_text(
        "#### human\n\nfix the auth bug\n\n"
        "#### assistant\n\nHere's what I found in auth.py...\n\n"
    )
    from bookmark.capture.agents.aider import read_recent_transcript
    result = read_recent_transcript(str(tmp_path))
    assert len(result) == 2
    assert result[0]["role"] == "user"
    assert "fix the auth bug" in result[0]["content"]
    assert result[1]["role"] == "assistant"


def test_aider_reader_empty_when_no_file(tmp_path):
    from bookmark.capture.agents.aider import read_recent_transcript
    result = read_recent_transcript(str(tmp_path))
    assert result == []


def test_aider_reader_user_role(tmp_path):
    """'user' header is also recognized."""
    history = tmp_path / ".aider.chat.history.md"
    history.write_text(
        "#### user\n\nhelp me refactor\n\n"
        "#### assistant\n\nSure, here is the plan.\n\n"
    )
    from bookmark.capture.agents.aider import read_recent_transcript
    result = read_recent_transcript(str(tmp_path))
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "assistant"


def test_aider_reader_n_messages_limit(tmp_path):
    """n_messages parameter limits returned messages."""
    history = tmp_path / ".aider.chat.history.md"
    lines = []
    for i in range(10):
        lines.append(f"#### human\n\nmessage {i}\n")
        lines.append(f"#### assistant\n\nreply {i}\n")
    history.write_text("\n".join(lines))
    from bookmark.capture.agents.aider import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), n_messages=4)
    assert len(result) == 4


def test_get_agent_reader_returns_correct_type():
    from bookmark.capture.agents import get_agent_reader
    for source in ["claude-code", "cursor", "codex", "gemini", "aider", "github-copilot"]:
        reader = get_agent_reader(source)
        assert reader is not None, f"Expected reader for {source}"
        assert hasattr(reader, "read_recent_transcript"), f"Missing method for {source}"

    assert get_agent_reader("terminal") is None
    assert get_agent_reader("generic") is None


def test_codex_reader_empty_when_no_dir(tmp_path):
    from bookmark.capture.agents.codex import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), _base_dir=tmp_path)
    assert result == []


def test_codex_reader_finds_session(tmp_path):
    """Codex reader finds most recent session file."""
    sessions_dir = tmp_path / ".codex" / "sessions"
    sessions_dir.mkdir(parents=True)
    session_file = sessions_dir / "session-001.jsonl"
    lines = [
        json.dumps({"role": "user", "content": "write a test"}),
        json.dumps({"role": "assistant", "content": "Here is a test for you."}),
    ]
    session_file.write_text("\n".join(lines))

    from bookmark.capture.agents.codex import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), _base_dir=tmp_path)
    assert len(result) == 2
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "assistant"


def test_gemini_reader_empty_when_no_dir(tmp_path):
    from bookmark.capture.agents.gemini import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), _base_dir=tmp_path)
    assert result == []


def test_gemini_reader_finds_session(tmp_path):
    """Gemini reader finds session in .gemini/sessions dir."""
    sessions_dir = tmp_path / ".gemini" / "sessions"
    sessions_dir.mkdir(parents=True)
    session_file = sessions_dir / "session-001.jsonl"
    lines = [
        json.dumps({"role": "user", "content": "explain this code"}),
        json.dumps({"role": "assistant", "content": "This code does X."}),
    ]
    session_file.write_text("\n".join(lines))

    from bookmark.capture.agents.gemini import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), _base_dir=tmp_path)
    assert len(result) == 2
    assert result[0]["role"] == "user"


def test_github_copilot_reader_empty_when_no_storage(tmp_path):
    from bookmark.capture.agents.github_copilot import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), _base_dir=tmp_path)
    assert result == []


def test_github_copilot_reader_finds_session(tmp_path):
    """Copilot reader finds messages from VS Code workspaceStorage SQLite."""
    import sqlite3

    storage = tmp_path / ".config" / "Code" / "User" / "workspaceStorage" / "abc123"
    storage.mkdir(parents=True)
    db_path = storage / "state.vscdb"

    messages = [
        {"role": "user", "content": "how do I reverse a list?"},
        {"role": "assistant", "content": "Use list[::-1] or list.reverse()."},
    ]
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE ItemTable (key TEXT, value TEXT)")
    conn.execute(
        "INSERT INTO ItemTable VALUES (?, ?)",
        ("github.copilot-chat.history", json.dumps(messages)),
    )
    conn.commit()
    conn.close()

    from bookmark.capture.agents.github_copilot import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), _base_dir=tmp_path)
    assert len(result) == 2
    assert result[0]["role"] == "user"
    assert "reverse" in result[0]["content"]
    assert result[1]["role"] == "assistant"


def test_github_copilot_reader_n_messages_limit(tmp_path):
    """n_messages parameter limits returned messages."""
    import sqlite3

    storage = tmp_path / ".config" / "Code" / "User" / "workspaceStorage" / "def456"
    storage.mkdir(parents=True)
    db_path = storage / "state.vscdb"

    messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"} for i in range(10)]
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE ItemTable (key TEXT, value TEXT)")
    conn.execute("INSERT INTO ItemTable VALUES (?, ?)", ("github.copilot-chat.history", json.dumps(messages)))
    conn.commit()
    conn.close()

    from bookmark.capture.agents.github_copilot import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), n_messages=4, _base_dir=tmp_path)
    assert len(result) == 4


# --- JetBrains ---

def _make_jetbrains_options(tmp_path, product="IntelliJIdea2024.3") -> Path:
    """Create a fake JetBrains options directory under tmp_path."""
    options = tmp_path / ".config" / "JetBrains" / product / "options"
    options.mkdir(parents=True)
    return options



def test_jetbrains_reader_empty_when_no_config(tmp_path):
    from bookmark.capture.agents.jetbrains import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), _base_dir=tmp_path)
    assert result == []


def test_jetbrains_reader_finds_messages_in_xml_attribute(tmp_path):
    """Reader extracts messages from JSON stored in an XML attribute value."""
    import xml.etree.ElementTree as ET

    options = _make_jetbrains_options(tmp_path)
    messages = [
        {"role": "user", "content": "explain decorators"},
        {"role": "assistant", "content": "Decorators wrap functions."},
    ]
    xml_path = options / "github.copilot.xml"
    # Build XML with the JSON as an attribute value
    root = ET.Element("application")
    comp = ET.SubElement(root, "component", name="GitHubCopilotChat")
    ET.SubElement(comp, "option", name="chatHistory", value=json.dumps(messages))
    ET.ElementTree(root).write(str(xml_path), encoding="unicode")

    from bookmark.capture.agents.jetbrains import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), _base_dir=tmp_path)
    assert len(result) == 2
    assert result[0]["role"] == "user"
    assert "decorator" in result[0]["content"]
    assert result[1]["role"] == "assistant"


def test_jetbrains_reader_finds_messages_in_xml_text(tmp_path):
    """Reader extracts messages from JSON stored as element text."""
    import xml.etree.ElementTree as ET

    options = _make_jetbrains_options(tmp_path)
    messages = [
        {"role": "user", "content": "what is a monad?"},
        {"role": "assistant", "content": "A monad is a design pattern."},
    ]
    xml_path = options / "github.copilot.xml"
    root = ET.Element("application")
    comp = ET.SubElement(root, "component", name="GitHubCopilotChat")
    history = ET.SubElement(comp, "chatHistory")
    history.text = json.dumps(messages)
    ET.ElementTree(root).write(str(xml_path), encoding="unicode")

    from bookmark.capture.agents.jetbrains import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), _base_dir=tmp_path)
    assert len(result) == 2
    assert result[0]["role"] == "user"


def test_jetbrains_reader_wrapped_dict_format(tmp_path):
    """Reader handles JSON wrapped in a dict with a known key."""
    import xml.etree.ElementTree as ET

    options = _make_jetbrains_options(tmp_path)
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    wrapped = {"history": messages}
    xml_path = options / "github.copilot.xml"
    root = ET.Element("application")
    ET.SubElement(root, "option", name="data", value=json.dumps(wrapped))
    ET.ElementTree(root).write(str(xml_path), encoding="unicode")

    from bookmark.capture.agents.jetbrains import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), _base_dir=tmp_path)
    assert len(result) == 2


def test_jetbrains_reader_n_messages_limit(tmp_path):
    import xml.etree.ElementTree as ET

    options = _make_jetbrains_options(tmp_path)
    messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"} for i in range(10)]
    xml_path = options / "github.copilot.xml"
    root = ET.Element("application")
    ET.SubElement(root, "option", name="h", value=json.dumps(messages))
    ET.ElementTree(root).write(str(xml_path), encoding="unicode")

    from bookmark.capture.agents.jetbrains import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), n_messages=3, _base_dir=tmp_path)
    assert len(result) == 3


def test_jetbrains_reader_searches_multiple_products(tmp_path):
    """Picks the most recently modified product's options dir."""
    import time
    import xml.etree.ElementTree as ET

    older = _make_jetbrains_options(tmp_path, "PyCharm2023.1")
    newer = _make_jetbrains_options(tmp_path, "IntelliJIdea2024.3")

    old_msgs = [{"role": "user", "content": "old message"}]
    new_msgs = [
        {"role": "user", "content": "new question"},
        {"role": "assistant", "content": "new answer"},
    ]

    for options, msgs in [(older, old_msgs), (newer, new_msgs)]:
        xml_path = options / "github.copilot.xml"
        root = ET.Element("application")
        ET.SubElement(root, "option", name="h", value=json.dumps(msgs))
        ET.ElementTree(root).write(str(xml_path), encoding="unicode")

    # Touch newer dir to ensure its mtime is later
    time.sleep(0.01)
    (newer / "github.copilot.xml").touch()

    from bookmark.capture.agents.jetbrains import read_recent_transcript
    result = read_recent_transcript(str(tmp_path), _base_dir=tmp_path)
    assert result[0]["content"] == "new question"


def test_get_agent_reader_includes_jetbrains():
    from bookmark.capture.agents import get_agent_reader
    reader = get_agent_reader("jetbrains")
    assert reader is not None
    assert hasattr(reader, "read_recent_transcript")
