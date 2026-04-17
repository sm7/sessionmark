"""Export paste tests — §11.5 of design doc."""


def test_export_generic_paste(tmp_path, monkeypatch):
    from bookmark.core.models import Bookmark, FileEntry, TodoItem
    from bookmark.export.paste import render_paste

    bm = Bookmark(name="test", slug="test", repo_root="/tmp", goal="fix the bug", source="terminal")
    todos = [TodoItem(text="check the logs", origin="TODO.md", status="pending")]
    transcript = [
        {"role": "user", "content": "what's wrong?"},
        {"role": "assistant", "content": "the auth token is expired"},
    ]
    open_files = [FileEntry(path="src/auth.py", status="M")]

    output = render_paste(bm, todos, transcript, open_files, target="generic")
    assert "fix the bug" in output
    assert "check the logs" in output
    assert "src/auth.py" in output
    assert "acknowledge" in output.lower()  # must end with acknowledgment request


def test_export_claude_differs_from_generic(tmp_path):
    from bookmark.core.models import Bookmark
    from bookmark.export.paste import render_paste
    bm = Bookmark(name="test", slug="test", repo_root="/tmp", goal="fix the bug", source="terminal")
    generic = render_paste(bm, [], [], [], target="generic")
    claude = render_paste(bm, [], [], [], target="claude")
    assert generic != claude


def test_export_all_targets_valid(tmp_path):
    from bookmark.core.models import Bookmark
    from bookmark.export.paste import render_paste, VALID_TARGETS
    bm = Bookmark(name="test", slug="test", repo_root="/tmp", goal="goal", source="terminal")
    for target in VALID_TARGETS:
        result = render_paste(bm, [], [], [], target=target)
        assert len(result) > 50  # non-trivial output


def test_export_unknown_target_falls_back_to_generic(tmp_path):
    from bookmark.core.models import Bookmark
    from bookmark.export.paste import render_paste
    bm = Bookmark(name="test", slug="test", repo_root="/tmp", goal="goal", source="terminal")
    result = render_paste(bm, [], [], [], target="unknown-agent")
    assert len(result) > 50  # falls back to generic, doesn't crash
